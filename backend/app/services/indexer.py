"""
Shared indexing logic for importing email files into the database.
Used by both the upload API endpoint and the folder watcher.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path

from app.config import SUPPORTED_FORMATS
from app.database import get_db, get_connection
from app.services.parser import parse_email_file
from app.services.projects import get_active_project, get_project_attachments_dir

logger = logging.getLogger(__name__)

# In-memory job tracking
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_cancel_events: dict[str, threading.Event] = {}


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _update_job(job_id: str, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def cancel_job(job_id: str) -> bool:
    """Signal a running import job to stop. Returns True if the job was found and signalled."""
    with _jobs_lock:
        event = _cancel_events.get(job_id)
        if event:
            event.set()
            return True
    return False


def import_email_file(
    file_path: str,
    file_source: str | None = None,
    job_id: str | None = None,
    project_slug: str | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """
    Parse and index an email file into the database.

    Args:
        file_path: Path to the email file on disk.
        file_source: Display name for the source (defaults to filename).
        job_id: Optional job ID for progress tracking.
        project_slug: Target project (defaults to active project).

    Returns:
        Dict with keys: imported, skipped, errors, filename.
    """
    if file_source is None:
        file_source = os.path.basename(file_path)

    slug = project_slug or get_active_project()
    att_base = get_project_attachments_dir(slug)
    os.makedirs(att_base, exist_ok=True)

    ext = Path(file_path).suffix.lower()
    format_type = SUPPORTED_FORMATS.get(ext)
    if not format_type:
        raise ValueError(f"Unsupported format: {ext}. Supported: {', '.join(SUPPORTED_FORMATS.keys())}")

    imported = 0
    skipped = 0
    errors = 0
    processed = 0
    last_log_time = time.time()

    logger.info(f"Starting import: {file_source} → project:{slug}")

    # Log to activity system
    try:
        from app.services.activity_log import log_activity
        log_activity("info", "import", f"Starting import: {file_source}", project=slug)
    except Exception:
        pass

    BATCH_SIZE = 500
    conn = get_connection(slug)

    # Bulk-loading pragmas
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")  # 64MB
    conn.execute("PRAGMA temp_store = MEMORY")

    # Disable FTS triggers during bulk import — we'll rebuild at the end
    try:
        conn.execute("DROP TRIGGER IF EXISTS emails_ai")
        conn.commit()
        fts_deferred = True
    except Exception:
        fts_deferred = False

    try:
        for parsed in parse_email_file(file_path, format_type):
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                conn.commit()
                logger.info(f"Import cancelled [{file_source}]: {processed} processed, {imported} imported")
                if job_id:
                    _update_job(job_id, status="cancelled", processed=processed,
                                imported=imported, skipped=skipped, errors=errors)
                break

            processed += 1
            now = time.time()
            if now - last_log_time >= 5:
                logger.info(
                    f"Import progress [{file_source}]: "
                    f"{processed} processed, {imported} imported, {skipped} skipped, {errors} errors"
                )
                last_log_time = now
                if job_id:
                    _update_job(job_id, processed=processed, imported=imported,
                                skipped=skipped, errors=errors)
                # Activity log progress
                try:
                    from app.services.activity_log import log_activity
                    log_activity(
                        "info", "import",
                        f"Import progress [{file_source}]: {processed} processed, {imported} imported",
                        project=slug,
                    )
                except Exception:
                    pass

            try:
                # Check for duplicates by message_id
                if parsed.message_id:
                    existing = conn.execute(
                        "SELECT id FROM emails WHERE message_id = ?",
                        (parsed.message_id,)
                    ).fetchone()
                    if existing:
                        skipped += 1
                        continue

                date_str = parsed.date.isoformat() if parsed.date else None
                date_unix = parsed.date.timestamp() if parsed.date else None

                cursor = conn.execute(
                    """INSERT INTO emails
                    (file_source, message_id, subject, sender, sender_name,
                     recipients, cc, bcc, date, date_unix,
                     body_text, body_html, has_attachments, raw_headers, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        file_source,
                        parsed.message_id,
                        parsed.subject,
                        parsed.sender,
                        parsed.sender_name,
                        parsed.recipients,
                        parsed.cc,
                        parsed.bcc,
                        date_str,
                        date_unix,
                        parsed.body_text,
                        parsed.body_html,
                        1 if parsed.has_attachments else 0,
                        parsed.raw_headers,
                        parsed.content_hash,
                    ),
                )
                email_id = cursor.lastrowid

                # Save attachments to project directory
                for att in parsed.attachments:
                    att_dir = os.path.join(att_base, str(email_id))
                    os.makedirs(att_dir, exist_ok=True)
                    safe_filename = "".join(
                        c if c.isalnum() or c in "._- " else "_"
                        for c in att.filename
                    )
                    att_path = os.path.join(att_dir, safe_filename)
                    with open(att_path, "wb") as af:
                        af.write(att.data)

                    conn.execute(
                        """INSERT INTO attachments
                        (email_id, filename, content_type, size, file_path)
                        VALUES (?, ?, ?, ?, ?)""",
                        (email_id, att.filename, att.content_type, att.size, att_path),
                    )

                imported += 1
            except Exception as e:
                logger.warning(f"Failed to index email: {e}")
                errors += 1

            # Batch commit every N emails to keep WAL small and data visible
            if processed % BATCH_SIZE == 0:
                conn.commit()

        # Final commit for remaining rows
        conn.commit()

    finally:
        # Rebuild FTS index from scratch and restore trigger
        if fts_deferred:
            logger.info(f"Rebuilding FTS index for [{file_source}]...")
            if job_id:
                _update_job(job_id, processed=processed, imported=imported,
                            skipped=skipped, errors=errors)
            try:
                conn.execute("INSERT INTO emails_fts(emails_fts) VALUES('rebuild')")
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
                        INSERT INTO emails_fts(rowid, subject, sender, sender_name, recipients, body_text)
                        VALUES (new.id, new.subject, new.sender, new.sender_name, new.recipients, new.body_text);
                    END
                """)
                conn.commit()
                logger.info(f"FTS index rebuilt for [{file_source}]")
            except Exception as e:
                logger.warning(f"FTS rebuild failed: {e}")

        # Restore default pragmas
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute("PRAGMA cache_size = -2000")  # default

    logger.info(
        f"Import complete [{file_source}]: "
        f"{processed} processed, {imported} imported, {skipped} skipped, {errors} errors"
    )

    # Log completion
    try:
        from app.services.activity_log import log_activity
        log_activity(
            "success", "import",
            f"Import complete [{file_source}]: {imported} imported, {skipped} skipped, {errors} errors",
            project=slug,
            details={"imported": imported, "skipped": skipped, "errors": errors},
        )
    except Exception:
        pass

    result = {
        "filename": file_source,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }

    if job_id:
        _update_job(job_id, status="done", **result)

    return result


def start_import_job(file_path: str, file_source: str, project_slug: str | None = None) -> str:
    """Start an import in a background thread. Returns a job ID for polling."""
    job_id = uuid.uuid4().hex[:12]
    slug = project_slug or get_active_project()
    cancel_event = threading.Event()
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "filename": file_source,
            "project": slug,
            "status": "running",
            "processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
        }
        _cancel_events[job_id] = cancel_event

    def _run():
        try:
            import_email_file(file_path, file_source=file_source, job_id=job_id,
                              project_slug=slug, cancel_event=cancel_event)
        except Exception as e:
            logger.error(f"Background import failed [{file_source}]: {e}")
            _update_job(job_id, status="error", error=str(e))
            try:
                from app.services.activity_log import log_activity
                log_activity("error", "import", f"Import failed [{file_source}]: {e}", project=slug)
            except Exception:
                pass
        finally:
            with _jobs_lock:
                _cancel_events.pop(job_id, None)

    thread = threading.Thread(target=_run, daemon=True, name=f"import-{job_id}")
    thread.start()
    return job_id
