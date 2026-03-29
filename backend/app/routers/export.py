"""Export router: JSON, ZIP, and image export of emails."""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_project
from app.services.search import parse_search_query, build_search_sql
from app.services.export import (
    export_as_json,
    export_as_zip,
    render_email_image,
    export_images_zip,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    email_ids: list[int] | None = None
    search_query: str | None = None
    starred_only: bool = False
    include_forensics: bool = False


def _fetch_emails(req: ExportRequest, project_slug: str) -> list[dict]:
    """Fetch emails based on export criteria."""
    with get_db(project_slug) as conn:
        if req.email_ids:
            placeholders = ",".join("?" for _ in req.email_ids)
            where = f"WHERE id IN ({placeholders})"
            params = list(req.email_ids)
            if req.starred_only:
                where += " AND is_starred = 1"
            rows = conn.execute(
                f"SELECT * FROM emails {where} ORDER BY date_unix DESC",
                params,
            ).fetchall()
        elif req.search_query:
            search = parse_search_query(req.search_query)
            select_sql, _, params = build_search_sql(search, starred_only=req.starred_only)
            rows = conn.execute(select_sql, params).fetchall()
        elif req.starred_only:
            rows = conn.execute(
                "SELECT * FROM emails WHERE is_starred = 1 ORDER BY date_unix DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM emails ORDER BY date_unix DESC"
            ).fetchall()

    return [dict(r) for r in rows]


@router.post("/json")
def export_json(req: ExportRequest, project_slug: str = Depends(get_current_project)):
    """Export emails as JSON download."""
    rows = _fetch_emails(req, project_slug)
    if not rows:
        raise HTTPException(404, "No emails match the export criteria")

    data = export_as_json(rows, include_forensics=req.include_forensics)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=emails.json"},
    )


@router.post("/zip")
def export_zip(req: ExportRequest, project_slug: str = Depends(get_current_project)):
    """Export emails as a ZIP file containing .eml files."""
    rows = _fetch_emails(req, project_slug)
    if not rows:
        raise HTTPException(404, "No emails match the export criteria")

    data = export_as_zip(rows)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=emails.zip"},
    )


@router.get("/image/{email_id}")
def export_image(email_id: int, project_slug: str = Depends(get_current_project)):
    """Export a single email as a PNG image."""
    with get_db(project_slug) as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Email not found")

    img_data = render_email_image(dict(row))
    if not img_data:
        raise HTTPException(500, "Failed to render email as image")

    return StreamingResponse(
        io.BytesIO(img_data),
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename=email_{email_id}.png"
        },
    )


@router.post("/images")
def export_images(req: ExportRequest, project_slug: str = Depends(get_current_project)):
    """Export multiple emails as images in a ZIP file."""
    rows = _fetch_emails(req, project_slug)
    if not rows:
        raise HTTPException(404, "No emails match the export criteria")

    data = export_images_zip(rows)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=email_images.zip"},
    )
