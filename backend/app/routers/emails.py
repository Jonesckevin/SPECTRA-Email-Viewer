"""Emails router: list, view, and manage emails."""
from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse

from app.database import get_db
from app.dependencies import get_current_project

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
def list_emails(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    starred: bool = Query(False),
    sort: str = Query("date_desc", regex="^(date_asc|date_desc|subject_asc|subject_desc)$"),
    project_slug: str = Depends(get_current_project),
):
    """List emails with pagination."""
    order_map = {
        "date_desc": "e.date_unix DESC NULLS LAST",
        "date_asc": "e.date_unix ASC NULLS LAST",
        "subject_asc": "e.subject ASC",
        "subject_desc": "e.subject DESC",
    }
    order = order_map.get(sort, "e.date_unix DESC NULLS LAST")
    offset = (page - 1) * per_page

    with get_db(project_slug) as conn:
        where = "WHERE e.is_starred = 1" if starred else ""
        count = conn.execute(f"SELECT COUNT(*) FROM emails e {where}").fetchone()[0]
        rows = conn.execute(
            f"""SELECT e.*, e.subject as subject_highlight
                FROM emails e {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            (per_page, offset),
        ).fetchall()

    emails = []
    for row in rows:
        emails.append({
            "id": row["id"],
            "file_source": row["file_source"],
            "message_id": row["message_id"] or "",
            "subject": row["subject"] or "",
            "subject_highlight": row["subject_highlight"] or "",
            "sender": row["sender"] or "",
            "sender_name": row["sender_name"] or "",
            "recipients": row["recipients"] or "",
            "cc": row["cc"] or "",
            "bcc": row["bcc"] or "",
            "date": row["date"],
            "has_attachments": bool(row["has_attachments"]),
            "is_starred": bool(row["is_starred"]),
        })

    return {
        "emails": emails,
        "total": count,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (count + per_page - 1) // per_page),
    }


@router.get("/{email_id}")
def get_email(email_id: int, project_slug: str = Depends(get_current_project)):
    """Get a single email with full body and attachments."""
    with get_db(project_slug) as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Email not found")

        attachments = conn.execute(
            "SELECT id, filename, content_type, size FROM attachments WHERE email_id = ?",
            (email_id,),
        ).fetchall()

    return {
        "id": row["id"],
        "file_source": row["file_source"],
        "message_id": row["message_id"] or "",
        "subject": row["subject"] or "",
        "sender": row["sender"] or "",
        "sender_name": row["sender_name"] or "",
        "recipients": row["recipients"] or "",
        "cc": row["cc"] or "",
        "bcc": row["bcc"] or "",
        "date": row["date"],
        "body_text": row["body_text"] or "",
        "body_html": row["body_html"] or "",
        "has_attachments": bool(row["has_attachments"]),
        "is_starred": bool(row["is_starred"]),
        "imported_at": row["imported_at"],
        "attachments": [
            {
                "id": a["id"],
                "filename": a["filename"],
                "content_type": a["content_type"],
                "size": a["size"],
            }
            for a in attachments
        ],
    }


@router.get("/attachment/{attachment_id}")
def download_attachment(attachment_id: int, project_slug: str = Depends(get_current_project)):
    """Download an attachment file."""
    with get_db(project_slug) as conn:
        att = conn.execute(
            "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        if not att:
            raise HTTPException(404, "Attachment not found")

    file_path = att["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(404, "Attachment file missing from disk")

    return FileResponse(
        path=file_path,
        filename=att["filename"],
        media_type=att["content_type"] or "application/octet-stream",
    )


@router.delete("/{email_id}")
def delete_email(email_id: int, project_slug: str = Depends(get_current_project)):
    """Delete an email and its attachments."""
    with get_db(project_slug) as conn:
        row = conn.execute("SELECT id FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Email not found")

        # Delete attachment files
        attachments = conn.execute(
            "SELECT file_path FROM attachments WHERE email_id = ?", (email_id,)
        ).fetchall()
        for att in attachments:
            try:
                os.unlink(att["file_path"])
            except OSError:
                pass

        conn.execute("DELETE FROM attachments WHERE email_id = ?", (email_id,))
        conn.execute("DELETE FROM emails WHERE id = ?", (email_id,))

    return {"status": "ok"}
