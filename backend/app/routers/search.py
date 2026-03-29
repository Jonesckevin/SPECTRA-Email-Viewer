"""Search router: full-text search with Gmail-like syntax."""
from __future__ import annotations

import re
from fastapi import APIRouter, Query, Depends

from app.database import get_db
from app.dependencies import get_current_project
from app.services.search import parse_search_query, build_search_sql

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search_emails(
    q: str = Query("", description="Search query using Gmail-like syntax"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    starred_only: bool = Query(False),
    project_slug: str = Depends(get_current_project),
):
    """
    Search emails using advanced query syntax.

    Supports:
      - Field operators: from:, to:, subject:, body:, filename:
      - Date filters: before:YYYY-MM-DD, after:YYYY-MM-DD, date:YYYY-MM-DD
      - Status: is:starred, has:attachment
      - Boolean: AND, OR, NOT, -prefix
      - Phrase: "exact phrase"
      - Regex: regex:/pattern/
      - Grouping: (A OR B) AND C
    """
    if not q.strip():
        # No search query — return all emails (optionally starred)
        from app.routers.emails import list_emails
        return list_emails(page=page, per_page=per_page, starred=starred_only, project_slug=project_slug)

    search = parse_search_query(q)
    select_sql, count_sql, params = build_search_sql(search, starred_only=starred_only)

    offset = (page - 1) * per_page

    with get_db(project_slug) as conn:
        count_row = conn.execute(count_sql, params).fetchone()
        total = count_row[0] if count_row else 0

        paginated_sql = f"{select_sql} LIMIT ? OFFSET ?"
        rows = conn.execute(paginated_sql, params + [per_page, offset]).fetchall()

    # Apply regex post-filter if needed
    results = []
    for row in rows:
        if search.regex_patterns:
            combined_text = f"{row['subject']} {row['sender']} {row['body_text']}"
            match = all(
                re.search(pat, combined_text, re.IGNORECASE)
                for pat in search.regex_patterns
            )
            if not match:
                continue

        results.append({
            "id": row["id"],
            "file_source": row["file_source"],
            "message_id": row["message_id"] or "",
            "subject": row["subject"] or "",
            "subject_highlight": row["subject_highlight"] or row["subject"] or "",
            "sender": row["sender"] or "",
            "sender_name": row["sender_name"] or "",
            "recipients": row["recipients"] or "",
            "cc": row["cc"] or "",
            "bcc": row["bcc"] or "",
            "date": row["date"],
            "has_attachments": bool(row["has_attachments"]),
            "is_starred": bool(row["is_starred"]),
        })

    # If regex filtering reduced results, total count may be inaccurate
    if search.regex_patterns:
        total = len(results)

    return {
        "emails": results,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "query": q,
        "parsed": {
            "fts_query": search.fts_query,
            "has_errors": search.has_errors,
            "error_message": search.error_message,
        },
    }
