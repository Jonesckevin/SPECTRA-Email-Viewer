"""Upload router: handles email file uploads, indexing, and file browsing."""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import SUPPORTED_FORMATS, UPLOAD_DIR, MAX_UPLOAD_SIZE
from app.services.indexer import import_email_file, start_import_job, get_job, cancel_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("")
async def upload_email_file(file: UploadFile = File(...)):
    """Upload and index an email file (EML, MBOX, PST, OST, MSG)."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            400,
            f"Unsupported format: {ext}. Supported: {', '.join(SUPPORTED_FORMATS.keys())}"
        )

    # Save uploaded file to disk
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(413, f"File too large. Max: {MAX_UPLOAD_SIZE // (1024*1024)}MB")

        with open(save_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {e}")

    try:
        result = import_email_file(save_path, file_source=file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(500, f"Import failed: {e}")

    return {"status": "ok", **result}


@router.get("/files")
def list_uploaded_files():
    """List email files already present in the uploads directory."""
    files = []
    try:
        for entry in os.scandir(UPLOAD_DIR):
            if not entry.is_file():
                continue
            ext = Path(entry.name).suffix.lower()
            if ext not in SUPPORTED_FORMATS:
                continue
            stat = entry.stat()
            files.append({
                "name": entry.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    except OSError:
        pass

    files.sort(key=lambda f: f["modified"], reverse=True)
    return {"files": files}


class ImportRequest(BaseModel):
    filename: str


@router.post("/import")
def import_existing_file(req: ImportRequest):
    """Start importing an existing file from the uploads directory. Returns a job ID for polling."""
    # Prevent path traversal
    safe_name = os.path.basename(req.filename)
    if safe_name != req.filename:
        raise HTTPException(400, "Invalid filename")

    file_path = os.path.join(UPLOAD_DIR, safe_name)
    if not os.path.isfile(file_path):
        raise HTTPException(404, "File not found in uploads")

    ext = Path(safe_name).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"Unsupported format: {ext}")

    job_id = start_import_job(file_path, file_source=safe_name)
    return {"status": "accepted", "job_id": job_id}


@router.get("/import/{job_id}")
def get_import_status(job_id: str):
    """Poll the progress of a background import job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/import/{job_id}/stop")
def stop_import_job(job_id: str):
    """Force-stop a running import job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") != "running":
        return {"status": "ok", "message": "Job is not running"}
    cancelled = cancel_job(job_id)
    if not cancelled:
        raise HTTPException(500, "Failed to cancel job")
    return {"status": "ok", "message": "Stop signal sent"}
