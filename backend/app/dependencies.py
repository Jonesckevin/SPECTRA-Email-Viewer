"""
FastAPI dependencies for project context resolution.
All routers that touch the project database use these dependencies.
"""
from __future__ import annotations

from fastapi import Header, Query

from app.services.projects import get_active_project


def get_current_project(
    x_project: str | None = Header(None, alias="X-Project"),
    project: str | None = Query(None),
) -> str:
    """
    Resolve the current project slug from request context.
    Checks X-Project header first, then ?project= query param, then falls back
    to the server-side active project.
    """
    if x_project:
        return x_project
    if project:
        return project
    return get_active_project()
