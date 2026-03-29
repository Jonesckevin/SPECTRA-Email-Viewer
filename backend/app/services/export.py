"""
Export service: JSON, ZIP (EML), and image (PNG) export of emails.
"""
from __future__ import annotations

import io
import json
import logging
import tempfile
import zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, formataddr
from typing import Any

from app.config import WKHTMLTOIMAGE_PATH

logger = logging.getLogger(__name__)


def email_to_dict(
    row: dict, include_body: bool = True, include_forensics: bool = False
) -> dict:
    """Convert an email DB row to an export-friendly dict."""
    d = {
        "id": row["id"],
        "message_id": row["message_id"] or "",
        "subject": row["subject"] or "",
        "sender": row["sender"] or "",
        "sender_name": row["sender_name"] or "",
        "recipients": row["recipients"] or "",
        "cc": row["cc"] or "",
        "bcc": row["bcc"] or "",
        "date": row["date"] or "",
        "has_attachments": bool(row["has_attachments"]),
        "is_starred": bool(row["is_starred"]),
    }
    if include_body:
        d["body_text"] = row["body_text"] or ""
        d["body_html"] = row["body_html"] or ""
    if include_forensics:
        d["raw_headers"] = row.get("raw_headers") or ""
        d["content_hash"] = row.get("content_hash") or ""
    return d


def export_as_json(rows: list[dict], include_forensics: bool = False) -> bytes:
    """Export emails as a JSON byte string."""
    emails = [email_to_dict(r, include_forensics=include_forensics) for r in rows]
    return json.dumps(emails, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def _build_eml(row: dict) -> bytes:
    """Reconstruct an .eml file from a DB row."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = row.get("subject") or ""
    msg["From"] = formataddr((row.get("sender_name") or "", row.get("sender") or ""))
    msg["To"] = row.get("recipients") or ""
    if row.get("cc"):
        msg["Cc"] = row["cc"]
    if row.get("bcc"):
        msg["Bcc"] = row["bcc"]
    if row.get("message_id"):
        msg["Message-ID"] = row["message_id"]
    if row.get("date"):
        msg["Date"] = row["date"]

    body_text = row.get("body_text") or ""
    body_html = row.get("body_html") or ""

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    return msg.as_bytes()


def export_as_zip(rows: list[dict]) -> bytes:
    """Export emails as a ZIP file containing .eml files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(rows):
            subject = (row.get("subject") or "no_subject")[:60]
            # Sanitize filename
            safe_subject = "".join(c if c.isalnum() or c in " _-." else "_" for c in subject)
            filename = f"{i + 1:04d}_{safe_subject}.eml"
            eml_data = _build_eml(row)
            zf.writestr(filename, eml_data)
    return buf.getvalue()


def render_email_image(row: dict) -> bytes | None:
    """Render an email as a PNG image using wkhtmltoimage."""
    import subprocess

    html = row.get("body_html") or ""
    if not html:
        # Wrap plain text in basic HTML
        body_text = row.get("body_text") or "(empty email)"
        html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>
body {{ font-family: sans-serif; padding: 20px; max-width: 800px; }}
</style></head><body><pre>{body_text}</pre></body></html>"""

    # Add email header info to the top of the HTML
    header_html = f"""
    <div style="font-family: sans-serif; padding: 20px; border-bottom: 2px solid #ddd; margin-bottom: 16px; max-width: 800px;">
        <h2 style="margin: 0 0 12px 0;">{_html_escape(row.get('subject') or '(no subject)')}</h2>
        <p style="margin: 4px 0; color: #555;"><strong>From:</strong> {_html_escape(row.get('sender_name') or '')} &lt;{_html_escape(row.get('sender') or '')}&gt;</p>
        <p style="margin: 4px 0; color: #555;"><strong>To:</strong> {_html_escape(row.get('recipients') or '')}</p>
        <p style="margin: 4px 0; color: #555;"><strong>Date:</strong> {_html_escape(row.get('date') or '')}</p>
    </div>
    """

    # Insert header into the HTML
    if "<body" in html.lower():
        import re
        html = re.sub(
            r'(<body[^>]*>)',
            rf'\1{header_html}',
            html,
            count=1,
            flags=re.IGNORECASE
        )
    else:
        html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>
body {{ font-family: sans-serif; padding: 20px; max-width: 800px; }}
img {{ max-width: 100%; }}
</style></head><body>{header_html}{html}</body></html>"""

    try:
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as hf:
            hf.write(html)
            html_path = hf.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as pf:
            png_path = pf.name

        result = subprocess.run(
            [WKHTMLTOIMAGE_PATH, "--quality", "90", "--width", "1024",
             "--disable-javascript", html_path, png_path],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error(f"wkhtmltoimage failed: {result.stderr.decode(errors='replace')}")
            return None

        with open(png_path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("wkhtmltoimage not found")
        return None
    except subprocess.TimeoutExpired:
        logger.error("wkhtmltoimage timed out")
        return None
    except Exception as e:
        logger.error(f"Image export failed: {e}")
        return None
    finally:
        import os
        for p in [html_path, png_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


def export_images_zip(rows: list[dict]) -> bytes:
    """Render multiple emails as images, return as a ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(rows):
            subject = (row.get("subject") or "no_subject")[:60]
            safe_subject = "".join(c if c.isalnum() or c in " _-." else "_" for c in subject)
            filename = f"{i + 1:04d}_{safe_subject}.png"
            img_data = render_email_image(row)
            if img_data:
                zf.writestr(filename, img_data)
    return buf.getvalue()


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
