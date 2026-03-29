"""
Search query parser using Lark grammar.
Supports Gmail-like syntax:
  - Field operators: from:, to:, subject:, body:, filename:
  - Date filters: before:, after:, date:
  - Status filters: is:starred, has:attachment
  - Boolean: AND, OR, NOT, - (negation prefix)
  - Phrase: "exact phrase"
  - Regex: regex:/pattern/
  - Grouping: (A OR B) AND C
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

from lark import Lark, Transformer, v_args, Token

logger = logging.getLogger(__name__)

GRAMMAR = r"""
    start: expr

    ?expr: or_expr

    ?or_expr: and_expr (OR and_expr)*

    ?and_expr: not_expr (AND? not_expr)*

    ?not_expr: NOT atom    -> negation
        | MINUS atom       -> negation
        | atom

    ?atom: field_expr
        | paren_expr
        | regex_expr
        | phrase
        | word

    paren_expr: "(" expr ")"

    field_expr: FIELD_NAME ":" field_value

    field_value: phrase
        | FIELD_WORD

    regex_expr: "regex:" REGEX_PATTERN

    phrase: ESCAPED_STRING

    word: WORD

    FIELD_NAME: /(?:from|to|cc|bcc|subject|body|filename|date|before|after|is|has)/i
    FIELD_WORD: /[^\s()\"]+/
    WORD: /(?!(?:AND|OR|NOT)\b)[^\s()\"]+/i
    REGEX_PATTERN: "/" /[^\/]+/ "/"

    OR: /OR/i
    AND: /AND/i
    NOT: /NOT/i
    MINUS: "-"

    %import common.ESCAPED_STRING
    %import common.WS
    %ignore WS
"""

parser = Lark(GRAMMAR, parser="earley", ambiguity="resolve")


@dataclass
class SearchQuery:
    """Represents a parsed search query decomposed into parts."""
    fts_query: str = ""
    where_clauses: list[str] = field(default_factory=list)
    params: list[Any] = field(default_factory=list)
    regex_patterns: list[str] = field(default_factory=list)
    has_errors: bool = False
    error_message: str = ""


# FTS5 column mapping for field operators
FTS_FIELD_MAP = {
    "from": "sender",
    "to": "recipients",
    "cc": "recipients",
    "bcc": "recipients",
    "subject": "subject",
    "body": "body_text",
}


@v_args(inline=True)
class QueryTransformer(Transformer):
    """Transforms the parse tree into FTS5 query + SQL WHERE clauses."""

    def __init__(self):
        super().__init__()
        self.where_clauses: list[str] = []
        self.params: list[Any] = []
        self.regex_patterns: list[str] = []

    def start(self, expr):
        return expr

    def or_expr(self, *args):
        parts = [a for a in args if a and not str(a).startswith("__NEG__")]
        if len(parts) == 1:
            return parts[0]
        return " OR ".join(f"({p})" for p in parts)

    def and_expr(self, *args):
        positive = []
        negative = []
        for a in args:
            if not a:
                continue
            s = str(a)
            if s.startswith("__NEG__"):
                negative.append(s[7:])
            else:
                positive.append(s)

        # Build the FTS5 expression: positives joined with AND, then binary NOT for each negative
        result = " AND ".join(f"({p})" for p in positive) if positive else ""
        for neg in negative:
            if result:
                result = f"({result}) NOT ({neg})"
            else:
                # FTS5 can't negate without a positive term; skip
                logger.warning(f"Ignoring standalone negation: NOT {neg}")
        return result

    def negation(self, *args):
        # Tag negated content so and_expr can build FTS5 binary NOT
        content = args[-1]
        if content:
            return f"__NEG__{content}"
        return ""

    def paren_expr(self, expr):
        return f"({expr})"

    def word(self, token):
        text = str(token)
        # Escape FTS5 special characters
        safe = text.replace('"', '""')
        return f'"{safe}"'

    def phrase(self, token):
        # Remove surrounding quotes from ESCAPED_STRING
        text = str(token)[1:-1]
        text = text.replace('\\"', '"').replace('\\\\', '\\')
        safe = text.replace('"', '""')
        return f'"{safe}"'

    def field_value(self, token):
        text = str(token)
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        return text

    def field_expr(self, field_name, value):
        field_lower = str(field_name).lower()
        val = str(value)

        # Status filters → SQL WHERE
        if field_lower == "is":
            if val.lower() == "starred":
                self.where_clauses.append("e.is_starred = 1")
                return ""
            return ""

        if field_lower == "has":
            if val.lower() == "attachment":
                self.where_clauses.append("e.has_attachments = 1")
                return ""
            return ""

        # Date filters → SQL WHERE
        if field_lower in ("before", "after", "date"):
            op = {"before": "<", "after": ">", "date": "="}[field_lower]
            # If date: with a range like 2024-01-01..2024-12-31
            if ".." in val and field_lower == "date":
                parts = val.split("..", 1)
                self.where_clauses.append("e.date_unix >= ?")
                self.params.append(self._parse_date_value(parts[0]))
                self.where_clauses.append("e.date_unix <= ?")
                self.params.append(self._parse_date_value(parts[1], end_of_day=True))
                return ""
            ts = self._parse_date_value(val, end_of_day=(field_lower == "before"))
            if ts is not None:
                if field_lower == "date":
                    # Match the whole day
                    self.where_clauses.append("e.date_unix >= ?")
                    self.params.append(self._parse_date_value(val))
                    self.where_clauses.append("e.date_unix <= ?")
                    self.params.append(self._parse_date_value(val, end_of_day=True))
                else:
                    self.where_clauses.append(f"e.date_unix {op} ?")
                    self.params.append(ts)
            return ""

        # Filename filter → SQL WHERE on attachments table
        if field_lower == "filename":
            safe_val = val.replace("'", "''")
            self.where_clauses.append(
                f"e.id IN (SELECT email_id FROM attachments WHERE filename LIKE ?)"
            )
            self.params.append(f"%{safe_val}%")
            return ""

        # FTS field search
        fts_col = FTS_FIELD_MAP.get(field_lower)
        if fts_col:
            safe = val.replace('"', '""')
            return f'{fts_col} : "{safe}"'

        # Fallback: treat as body text search
        safe = val.replace('"', '""')
        return f'"{safe}"'

    def regex_expr(self, pattern_token):
        pattern = str(pattern_token)
        # Remove surrounding slashes if present
        if pattern.startswith("/") and pattern.endswith("/"):
            pattern = pattern[1:-1]
        # Validate the regex
        try:
            re.compile(pattern)
            self.regex_patterns.append(pattern)
        except re.error as e:
            logger.warning(f"Invalid regex pattern: {pattern} - {e}")
        return ""

    def _parse_date_value(self, val: str, end_of_day: bool = False) -> float | None:
        from dateutil import parser as dateutil_parser
        from datetime import datetime, timezone, timedelta
        try:
            dt = dateutil_parser.parse(val)
            if end_of_day:
                dt = dt.replace(hour=23, minute=59, second=59)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except (ValueError, OverflowError):
            return None

    # Handle tokens that Lark passes through
    def FIELD_NAME(self, token):
        return str(token)

    def FIELD_WORD(self, token):
        return str(token)

    def WORD(self, token):
        return str(token)

    def REGEX_PATTERN(self, token):
        return str(token)

    def OR(self, token):
        return None

    def AND(self, token):
        return None

    def NOT(self, token):
        return None

    def MINUS(self, token):
        return None


def parse_search_query(query_str: str) -> SearchQuery:
    """
    Parse a search query string into a SearchQuery object containing
    an FTS5 query, SQL WHERE clauses, and regex patterns.
    """
    query_str = query_str.strip()
    if not query_str:
        return SearchQuery()

    try:
        tree = parser.parse(query_str)
        transformer = QueryTransformer()
        fts_result = transformer.transform(tree)

        fts_query = str(fts_result).strip() if fts_result else ""
        # Clean up any leaked negation tags
        fts_query = fts_query.replace("__NEG__", "")
        # Clean up empty AND/OR clauses
        fts_query = re.sub(r'\(\s*\)', '', fts_query)
        fts_query = re.sub(r'\s+AND\s+AND\s+', ' AND ', fts_query)
        fts_query = re.sub(r'\s+OR\s+OR\s+', ' OR ', fts_query)
        fts_query = re.sub(r'^\s*(AND|OR)\s+', '', fts_query)
        fts_query = re.sub(r'\s+(AND|OR)\s*$', '', fts_query)
        fts_query = fts_query.strip()

        return SearchQuery(
            fts_query=fts_query,
            where_clauses=transformer.where_clauses,
            params=transformer.params,
            regex_patterns=transformer.regex_patterns,
        )
    except Exception as e:
        logger.warning(f"Failed to parse search query '{query_str}': {e}")
        # Fallback: treat the whole query as a plain text search
        safe = query_str.replace('"', '""')
        return SearchQuery(
            fts_query=f'"{safe}"',
            has_errors=True,
            error_message=str(e),
        )


def build_search_sql(search: SearchQuery, starred_only: bool = False) -> tuple[str, str, list]:
    """
    Build the complete SQL query from a parsed SearchQuery.
    Returns (select_sql, count_sql, params).
    """
    conditions = list(search.where_clauses)
    params = list(search.params)

    if starred_only:
        conditions.append("e.is_starred = 1")

    join_fts = ""
    order_by = "e.date_unix DESC"

    if search.fts_query:
        join_fts = "JOIN emails_fts ON e.id = emails_fts.rowid"
        conditions.append("emails_fts MATCH ?")
        params.append(search.fts_query)
        order_by = "emails_fts.rank, e.date_unix DESC"

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    select_sql = f"""
        SELECT e.*, highlight(emails_fts, 0, '<mark>', '</mark>') as subject_highlight
        FROM emails e
        {join_fts}
        {where}
        ORDER BY {order_by}
    """ if search.fts_query else f"""
        SELECT e.*, e.subject as subject_highlight
        FROM emails e
        {where}
        ORDER BY {order_by}
    """

    count_sql = f"""
        SELECT COUNT(*) FROM emails e
        {join_fts}
        {where}
    """

    return select_sql, count_sql, params
