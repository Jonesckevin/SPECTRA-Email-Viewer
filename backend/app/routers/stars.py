"""Star/favorite router: toggle and bulk star operations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_project

router = APIRouter(prefix="/api/stars", tags=["stars"])


class BulkStarRequest(BaseModel):
    email_ids: list[int]
    starred: bool


@router.post("/{email_id}/toggle")
def toggle_star(email_id: int, project_slug: str = Depends(get_current_project)):
    """Toggle the starred status of an email."""
    with get_db(project_slug) as conn:
        row = conn.execute("SELECT id, is_starred FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Email not found")

        new_state = 0 if row["is_starred"] else 1
        conn.execute("UPDATE emails SET is_starred = ? WHERE id = ?", (new_state, email_id))

    return {"id": email_id, "is_starred": bool(new_state)}


@router.post("/bulk")
def bulk_star(request: BulkStarRequest, project_slug: str = Depends(get_current_project)):
    """Set starred status for multiple emails at once."""
    if not request.email_ids:
        return {"updated": 0}

    with get_db(project_slug) as conn:
        placeholders = ",".join("?" for _ in request.email_ids)
        starred_val = 1 if request.starred else 0
        conn.execute(
            f"UPDATE emails SET is_starred = ? WHERE id IN ({placeholders})",
            [starred_val] + request.email_ids,
        )

    return {"updated": len(request.email_ids), "is_starred": request.starred}
