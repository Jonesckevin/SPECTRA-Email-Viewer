"""SPECTRA — FastAPI application."""
from __future__ import annotations

import logging
import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import PROJECTS_DIR, DATABASE_PATH
from app.database import init_db, get_db
from app.dependencies import get_current_project
from app.routers import emails, upload, search, stars, export, forensics, statistics
from app.routers import projects as projects_router
from app.routers import activity as activity_router
from app.services.activity_log import init_activity_db, log_activity
from app.services.projects import ensure_default_project, get_active_project
from app.services.watcher import start_watcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _migrate_legacy_data():
    """Migrate flat data/emails.db to data/projects/default/ if needed."""
    old_db = DATABASE_PATH
    default_dir = os.path.join(PROJECTS_DIR, "default")
    new_db = os.path.join(default_dir, "emails.db")

    if os.path.isfile(old_db) and not os.path.isfile(new_db):
        logger.info("Migrating legacy database to default project...")
        os.makedirs(default_dir, exist_ok=True)
        shutil.move(old_db, new_db)
        logger.info(f"Moved {old_db} → {new_db}")

        # Also migrate attachments if they exist in uploads/
        old_att = os.path.join("uploads", "attachments")
        new_att = os.path.join(default_dir, "attachments")
        if os.path.isdir(old_att) and not os.path.isdir(new_att):
            shutil.move(old_att, new_att)
            logger.info(f"Moved attachments → {new_att}")

        log_activity("info", "system", "Legacy data migrated to default project")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing activity log database...")
    init_activity_db()

    logger.info("Setting up projects...")
    ensure_default_project()
    _migrate_legacy_data()

    logger.info("Initializing default project database...")
    init_db("default")
    logger.info("Database ready.")

    # Mark any scan jobs left 'running' from a previous container lifecycle as stopped
    from app.routers.forensics import cleanup_stale_scans
    from app.services.projects import list_projects
    for proj in list_projects():
        if proj["has_db"]:
            cleanup_stale_scans(proj["slug"])
    logger.info("Stale scan cleanup done.")

    log_activity("info", "system", "SPECTRA started")

    logger.info("Starting folder watcher...")
    start_watcher()
    yield


app = FastAPI(
    title="SPECTRA",
    description="Suspicious Post & Email Capture Tool for Rapid Analysis",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Projects and activity first (no path conflicts)
app.include_router(projects_router.router)
app.include_router(activity_router.router)
# Forensics before emails (scan-suspicious must match before /{email_id})
app.include_router(forensics.router)
app.include_router(emails.router)
app.include_router(upload.router)
app.include_router(search.router)
app.include_router(stars.router)
app.include_router(export.router)
app.include_router(statistics.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def stats(project_slug: str = Depends(get_current_project)):
    with get_db(project_slug) as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        starred = conn.execute("SELECT COUNT(*) FROM emails WHERE is_starred = 1").fetchone()[0]
        with_attachments = conn.execute(
            "SELECT COUNT(*) FROM emails WHERE has_attachments = 1"
        ).fetchone()[0]
        sources = conn.execute(
            "SELECT DISTINCT file_source FROM emails"
        ).fetchall()
    return {
        "total_emails": total,
        "starred": starred,
        "with_attachments": with_attachments,
        "sources": [s[0] for s in sources],
    }
