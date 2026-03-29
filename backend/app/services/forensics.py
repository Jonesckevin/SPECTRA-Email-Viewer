"""
Forensic analysis service for email investigation.
Provides header parsing, authentication result extraction,
suspicious indicator detection, and hash computation.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Common free email providers
FREE_PROVIDERS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "mail.com", "protonmail.com", "icloud.com", "zoho.com", "yandex.com",
    "gmx.com", "live.com", "msn.com", "qq.com", "163.com", "126.com",
}


def compute_hashes(text: str) -> dict[str, str]:
    """Compute SHA-256, MD5, and SHA-1 hashes of text."""
    data = text.encode("utf-8", errors="replace")
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
    }


def compute_file_hash(file_path: str) -> dict[str, str]:
    """Compute SHA-256 hash of a file on disk."""
    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return {"sha256": h.hexdigest()}
    except Exception as e:
        logger.warning(f"Failed to hash file {file_path}: {e}")
        return {"sha256": "", "error": str(e)}


def parse_received_chain(raw_headers: str) -> list[dict[str, Any]]:
    """
    Parse Received headers into an ordered list of hops.
    Each hop contains: from_server, by_server, ip, timestamp, protocol.
    """
    if not raw_headers:
        return []

    hops = []
    # Extract all Received header values
    received_pattern = re.compile(
        r"^Received:\s*(.*?)(?=\n\S|\Z)", re.MULTILINE | re.DOTALL
    )
    matches = received_pattern.findall(raw_headers)

    for value in matches:
        # Clean up multiline values
        value = re.sub(r"\s+", " ", value).strip()
        hop: dict[str, Any] = {
            "from_server": "",
            "by_server": "",
            "ip": "",
            "timestamp": "",
            "protocol": "",
            "raw": value,
        }

        # Extract "from <server>"
        from_match = re.search(r"from\s+(\S+)", value, re.IGNORECASE)
        if from_match:
            hop["from_server"] = from_match.group(1)

        # Extract "by <server>"
        by_match = re.search(r"by\s+(\S+)", value, re.IGNORECASE)
        if by_match:
            hop["by_server"] = by_match.group(1)

        # Extract IP addresses (both IPv4 and IPv6)
        ip_match = re.search(
            r"\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]"
            r"|"
            r"\[((?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4})\]",
            value,
        )
        if ip_match:
            hop["ip"] = ip_match.group(1) or ip_match.group(2) or ""

        # Extract protocol (SMTP, ESMTP, etc.)
        proto_match = re.search(r"with\s+(E?SMTPS?A?)\b", value, re.IGNORECASE)
        if proto_match:
            hop["protocol"] = proto_match.group(1).upper()

        # Extract timestamp — usually after a semicolon
        ts_match = re.search(r";\s*(.+)$", value)
        if ts_match:
            ts_str = ts_match.group(1).strip()
            hop["timestamp"] = ts_str
            try:
                from dateutil import parser as dateutil_parser
                hop["parsed_time"] = dateutil_parser.parse(ts_str).isoformat()
            except Exception:
                hop["parsed_time"] = ""

        hops.append(hop)

    # Received headers are in reverse order (newest first), reverse to get oldest first
    hops.reverse()

    # Compute delays between consecutive hops
    for i in range(1, len(hops)):
        try:
            if hops[i].get("parsed_time") and hops[i - 1].get("parsed_time"):
                from dateutil import parser as dateutil_parser
                t1 = dateutil_parser.parse(hops[i - 1]["parsed_time"])
                t2 = dateutil_parser.parse(hops[i]["parsed_time"])
                delay = (t2 - t1).total_seconds()
                hops[i]["delay_seconds"] = round(delay, 1)
        except Exception:
            pass

    # Add hop numbers
    for i, hop in enumerate(hops):
        hop["hop_number"] = i + 1

    return hops


def extract_auth_results(raw_headers: str) -> dict[str, Any]:
    """
    Extract SPF, DKIM, and DMARC results from Authentication-Results headers.
    """
    results: dict[str, Any] = {
        "spf": {"result": "", "details": ""},
        "dkim": {"result": "", "details": ""},
        "dmarc": {"result": "", "details": ""},
        "raw": "",
    }

    if not raw_headers:
        return results

    # Find Authentication-Results header(s)
    auth_pattern = re.compile(
        r"^Authentication-Results:\s*(.*?)(?=\n\S|\Z)", re.MULTILINE | re.DOTALL
    )
    matches = auth_pattern.findall(raw_headers)

    if not matches:
        return results

    auth_text = " ".join(re.sub(r"\s+", " ", m).strip() for m in matches)
    results["raw"] = auth_text

    # Parse SPF
    spf_match = re.search(r"spf\s*=\s*(\w+)(?:\s+\(([^)]*)\))?", auth_text, re.IGNORECASE)
    if spf_match:
        results["spf"]["result"] = spf_match.group(1).lower()
        results["spf"]["details"] = spf_match.group(2) or ""

    # Parse DKIM
    dkim_match = re.search(r"dkim\s*=\s*(\w+)(?:\s+\(([^)]*)\))?", auth_text, re.IGNORECASE)
    if dkim_match:
        results["dkim"]["result"] = dkim_match.group(1).lower()
        results["dkim"]["details"] = dkim_match.group(2) or ""

    # Parse DMARC
    dmarc_match = re.search(r"dmarc\s*=\s*(\w+)(?:\s+\(([^)]*)\))?", auth_text, re.IGNORECASE)
    if dmarc_match:
        results["dmarc"]["result"] = dmarc_match.group(1).lower()
        results["dmarc"]["details"] = dmarc_match.group(2) or ""

    return results


def _get_header_value(raw_headers: str, header_name: str) -> str:
    """Extract a single header value from raw headers text."""
    pattern = re.compile(
        rf"^{re.escape(header_name)}:\s*(.*?)(?=\n\S|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(raw_headers)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def detect_suspicious_indicators(
    email_data: dict, raw_headers: str, received_chain: list[dict]
) -> list[dict[str, str]]:
    """
    Detect suspicious patterns in an email.
    Returns a list of indicator dicts with 'severity' and 'message' keys.
    Severity: 'high', 'medium', 'low'.
    """
    indicators: list[dict[str, str]] = []

    if not raw_headers:
        return indicators

    sender = email_data.get("sender", "")
    sender_domain = sender.split("@")[-1].lower() if "@" in sender else ""

    # 1. Reply-To differs from From
    reply_to = _get_header_value(raw_headers, "Reply-To")
    if reply_to:
        reply_addr = re.search(r"[\w.+-]+@[\w.-]+", reply_to)
        from_addr = re.search(r"[\w.+-]+@[\w.-]+", sender)
        if reply_addr and from_addr and reply_addr.group().lower() != from_addr.group().lower():
            indicators.append({
                "severity": "high",
                "message": f"Reply-To ({reply_addr.group()}) differs from From ({from_addr.group()})",
            })

    # 2. Sender uses free email provider but claims organization
    if sender_domain in FREE_PROVIDERS:
        sender_name = email_data.get("sender_name", "")
        org_keywords = ["inc", "corp", "llc", "ltd", "company", "enterprise", "bank", "security"]
        if sender_name and any(kw in sender_name.lower() for kw in org_keywords):
            indicators.append({
                "severity": "high",
                "message": f"Sender name suggests organization but uses free email provider ({sender_domain})",
            })

    # 3. Unusually long received chain (>8 hops)
    if len(received_chain) > 8:
        indicators.append({
            "severity": "medium",
            "message": f"Unusually long email routing chain ({len(received_chain)} hops)",
        })

    # 4. Large hop delay (>1 hour between any two hops)
    for hop in received_chain:
        delay = hop.get("delay_seconds")
        if delay is not None and delay > 3600:
            indicators.append({
                "severity": "medium",
                "message": f"Large delay ({delay:.0f}s) at hop {hop.get('hop_number', '?')}",
            })
            break  # Only report once

    # 5. Negative hop delay (time travel = possible forged header)
    for hop in received_chain:
        delay = hop.get("delay_seconds")
        if delay is not None and delay < -60:
            indicators.append({
                "severity": "high",
                "message": f"Negative time delay at hop {hop.get('hop_number', '?')} — possible forged Received header",
            })
            break

    # 6. X-Mailer or User-Agent anomalies
    x_mailer = _get_header_value(raw_headers, "X-Mailer")
    user_agent = _get_header_value(raw_headers, "User-Agent")
    mailer = x_mailer or user_agent
    if mailer:
        suspicious_mailers = ["phpmailer", "swiftmailer", "python", "curl", "wget"]
        if any(sm in mailer.lower() for sm in suspicious_mailers):
            indicators.append({
                "severity": "medium",
                "message": f"Unusual sending client: {mailer}",
            })

    # 7. Missing or empty Message-ID
    msg_id = email_data.get("message_id", "")
    if not msg_id or msg_id.startswith("<generated-"):
        indicators.append({
            "severity": "low",
            "message": "No original Message-ID (may indicate bulk/automated mail)",
        })

    # 8. X-Spam headers present
    spam_score = _get_header_value(raw_headers, "X-Spam-Score")
    spam_status = _get_header_value(raw_headers, "X-Spam-Status")
    if spam_score or spam_status:
        detail = spam_status or spam_score
        indicators.append({
            "severity": "low",
            "message": f"Spam detection header present: {detail[:100]}",
        })

    # 9. Mismatch between envelope and header From
    return_path = _get_header_value(raw_headers, "Return-Path")
    if return_path:
        rp_addr = re.search(r"[\w.+-]+@[\w.-]+", return_path)
        if rp_addr and sender:
            rp_domain = rp_addr.group().split("@")[-1].lower()
            if rp_domain != sender_domain and sender_domain:
                indicators.append({
                    "severity": "medium",
                    "message": f"Return-Path domain ({rp_domain}) differs from From domain ({sender_domain})",
                })

    return indicators
