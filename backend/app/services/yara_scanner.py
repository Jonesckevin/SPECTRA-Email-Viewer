"""
YARA scanning service.
Manages per-session YARA rules uploaded by the user.
Scans email content (body, headers, subject) against loaded rules.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_rules = None
_rules_lock = threading.Lock()
_rules_info: dict[str, Any] = {}

_yara_available = False
try:
    import yara
    _yara_available = True
except ImportError:
    logger.warning("yara-python not installed — YARA scanning disabled")


def is_available() -> bool:
    return _yara_available


def get_status() -> dict:
    """Get current YARA rules status."""
    with _rules_lock:
        if _rules is None:
            return {"loaded": False, "rule_count": 0, "filenames": []}
        return {
            "loaded": True,
            "rule_count": _rules_info.get("rule_count", 0),
            "filenames": _rules_info.get("filenames", []),
        }


def load_rules(file_data: bytes, filename: str = "rules.yar") -> dict:
    """Compile and load YARA rules from uploaded file data."""
    global _rules, _rules_info
    if not _yara_available:
        raise RuntimeError("yara-python is not installed")

    try:
        rules = yara.compile(source=file_data.decode("utf-8", errors="replace"))
    except yara.SyntaxError as e:
        raise ValueError(f"YARA syntax error: {e}")
    except Exception as e:
        raise ValueError(f"Failed to compile YARA rules: {e}")

    with _rules_lock:
        _rules = rules
        _rules_info = {
            "rule_count": len(list(rules)),
            "filenames": [filename],
        }

    logger.info(f"Loaded YARA rules from {filename}: {_rules_info['rule_count']} rules")
    return get_status()


def clear_rules() -> None:
    """Clear loaded YARA rules."""
    global _rules, _rules_info
    with _rules_lock:
        _rules = None
        _rules_info = {}
    logger.info("YARA rules cleared")


def scan_email(email_data: dict) -> list[dict]:
    """
    Scan an email against loaded YARA rules.
    Returns list of matches with rule name, tags, and matched strings.
    """
    with _rules_lock:
        rules = _rules

    if rules is None:
        return []

    # Build text to scan from email fields
    scan_parts = []
    for field in ("subject", "sender", "recipients", "body_text", "body_html", "raw_headers"):
        val = email_data.get(field, "")
        if val:
            scan_parts.append(str(val))
    scan_text = "\n".join(scan_parts)

    if not scan_text:
        return []

    try:
        matches = rules.match(data=scan_text.encode("utf-8", errors="replace"))
    except Exception as e:
        logger.warning(f"YARA scan error: {e}")
        return []

    results = []
    for match in matches:
        matched_strings = []
        try:
            for offset, identifier, data in match.strings:
                matched_strings.append({
                    "offset": offset,
                    "identifier": identifier,
                    "data": data.decode("utf-8", errors="replace")[:200],
                })
        except Exception:
            pass

        results.append({
            "rule": match.rule,
            "tags": list(match.tags) if match.tags else [],
            "severity": "high",
            "message": f"YARA rule matched: {match.rule}",
            "strings_matched": matched_strings[:10],
        })

    return results
