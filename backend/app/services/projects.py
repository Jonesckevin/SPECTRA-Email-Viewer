"""
Project/case management service.
Each project has its own SQLite database and attachments directory,
providing full isolation between forensic cases.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path

from app.config import PROJECTS_DIR

logger = logging.getLogger(__name__)

_active_project: str = "default"
_project_lock = threading.Lock()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:64] or "project"


def get_active_project() -> str:
    with _project_lock:
        return _active_project


def set_active_project(slug: str) -> None:
    global _active_project
    project_dir = os.path.join(PROJECTS_DIR, slug)
    if not os.path.isdir(project_dir):
        raise ValueError(f"Project not found: {slug}")
    with _project_lock:
        _active_project = slug
    logger.info(f"Active project set to: {slug}")


def get_project_dir(slug: str) -> str:
    return os.path.join(PROJECTS_DIR, slug)


def get_project_db_path(slug: str) -> str:
    return os.path.join(PROJECTS_DIR, slug, "emails.db")


def get_project_attachments_dir(slug: str) -> str:
    return os.path.join(PROJECTS_DIR, slug, "attachments")


def list_projects() -> list[dict]:
    projects = []
    if not os.path.isdir(PROJECTS_DIR):
        return projects

    for entry in sorted(os.scandir(PROJECTS_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        slug = entry.name
        db_path = os.path.join(entry.path, "emails.db")
        meta = {
            "slug": slug,
            "name": slug.replace("-", " ").title(),
            "path": entry.path,
            "has_db": os.path.isfile(db_path),
            "db_size": 0,
            "email_count": 0,
            "created_at": None,
        }

        try:
            stat = entry.stat()
            meta["created_at"] = stat.st_ctime
        except OSError:
            pass

        if meta["has_db"]:
            try:
                meta["db_size"] = os.path.getsize(db_path)
            except OSError:
                pass
            # Get email count from DB
            try:
                import sqlite3
                conn = sqlite3.connect(db_path)
                count = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
                meta["email_count"] = count
                conn.close()
            except Exception:
                pass

        projects.append(meta)

    return projects


def create_project(name: str) -> dict:
    slug = _slugify(name)
    project_dir = os.path.join(PROJECTS_DIR, slug)

    # Handle slug collision
    if os.path.exists(project_dir):
        slug = f"{slug}-{int(time.time()) % 10000}"
        project_dir = os.path.join(PROJECTS_DIR, slug)

    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "attachments"), exist_ok=True)

    # Initialize the database for this project
    from app.database import init_db
    init_db(slug)

    logger.info(f"Created project: {slug} at {project_dir}")
    return {"slug": slug, "name": name, "path": project_dir}


def delete_project(slug: str) -> None:
    if slug == "default":
        raise ValueError("Cannot delete the default project")

    project_dir = os.path.join(PROJECTS_DIR, slug)
    if not os.path.isdir(project_dir):
        raise ValueError(f"Project not found: {slug}")

    # Switch away if deleting active project
    if get_active_project() == slug:
        set_active_project("default")

    shutil.rmtree(project_dir)
    logger.info(f"Deleted project: {slug}")


def reset_project(slug: str) -> dict:
    """Delete all data in a project but keep the project directory."""
    project_dir = os.path.join(PROJECTS_DIR, slug)
    if not os.path.isdir(project_dir):
        raise ValueError(f"Project not found: {slug}")

    # Close any open connections to this project's DB
    from app.database import close_project_connections
    close_project_connections(slug)

    # Remove the database file
    db_path = get_project_db_path(slug)
    if os.path.isfile(db_path):
        os.remove(db_path)
    # Also remove WAL/SHM files
    for suffix in ("-wal", "-shm"):
        p = db_path + suffix
        if os.path.isfile(p):
            os.remove(p)

    # Clear attachments
    att_dir = get_project_attachments_dir(slug)
    if os.path.isdir(att_dir):
        shutil.rmtree(att_dir)
    os.makedirs(att_dir, exist_ok=True)

    # Re-initialize the database
    from app.database import init_db
    init_db(slug)

    logger.info(f"Reset project data: {slug}")
    return {"status": "ok", "slug": slug}


def ensure_default_project() -> None:
    default_dir = os.path.join(PROJECTS_DIR, "default")
    if not os.path.isdir(default_dir):
        os.makedirs(default_dir, exist_ok=True)
        os.makedirs(os.path.join(default_dir, "attachments"), exist_ok=True)
