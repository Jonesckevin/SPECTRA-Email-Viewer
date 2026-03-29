"""Projects router: CRUD for project/case management."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.projects import (
    list_projects,
    create_project,
    delete_project,
    reset_project,
    get_active_project,
    set_active_project,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str


@router.get("")
def get_projects():
    """List all projects with stats."""
    projects = list_projects()
    active = get_active_project()
    for p in projects:
        p["is_active"] = p["slug"] == active
    return {
        "projects": projects,
        "active": active,
    }


@router.post("")
def create_new_project(req: CreateProjectRequest):
    """Create a new project."""
    if not req.name.strip():
        raise HTTPException(400, "Project name is required")
    try:
        result = create_project(req.name)
    except Exception as e:
        raise HTTPException(500, f"Failed to create project: {e}")
    return result


@router.delete("/{slug}")
def delete_existing_project(slug: str):
    """Delete a project and all its data."""
    try:
        delete_project(slug)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "ok"}


@router.post("/{slug}/reset")
def reset_existing_project(slug: str):
    """Reset a project: delete all emails, attachments, and scan data, then reinitialize the DB."""
    try:
        result = reset_project(slug)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to reset project: {e}")
    return result


@router.post("/{slug}/activate")
def activate_project(slug: str):
    """Set the active project."""
    try:
        set_active_project(slug)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"status": "ok", "active": slug}


@router.get("/active")
def get_active():
    """Get the currently active project."""
    return {"active": get_active_project()}
