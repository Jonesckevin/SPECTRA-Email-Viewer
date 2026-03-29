"""
Folder watcher: monitors the watch directory for new email files
and auto-imports them. Files are moved to a 'processed' subfolder
after successful import.
"""
from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from pathlib import Path

from app.config import WATCH_DIR, SUPPORTED_FORMATS

logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.environ.get("WATCH_POLL_INTERVAL", "5"))  # seconds
_processed_dir = os.path.join(WATCH_DIR, "processed")
_failed_dir = os.path.join(WATCH_DIR, "failed")


def _ensure_dirs():
    os.makedirs(WATCH_DIR, exist_ok=True)
    os.makedirs(_processed_dir, exist_ok=True)
    os.makedirs(_failed_dir, exist_ok=True)


def _is_file_stable(file_path: str, wait: float = 2.0) -> bool:
    """Check if a file has finished being written by comparing sizes."""
    try:
        size1 = os.path.getsize(file_path)
        time.sleep(wait)
        size2 = os.path.getsize(file_path)
        return size1 == size2 and size1 > 0
    except OSError:
        return False


def _scan_and_import():
    """Scan the watch directory for new email files and import them."""
    from app.services.indexer import import_email_file
    from app.services.projects import get_active_project

    _ensure_dirs()

    for entry in os.scandir(WATCH_DIR):
        if not entry.is_file():
            continue

        ext = Path(entry.name).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            continue

        file_path = entry.path

        # Make sure the file is done being copied
        if not _is_file_stable(file_path):
            logger.debug(f"File still being written, skipping for now: {entry.name}")
            continue

        slug = get_active_project()
        logger.info(f"Auto-importing: {entry.name} → project:{slug}")

        try:
            from app.services.activity_log import log_activity
            log_activity("info", "import", f"Auto-importing: {entry.name}", project=slug)
        except Exception:
            pass

        try:
            result = import_email_file(file_path, file_source=entry.name, project_slug=slug)
            logger.info(
                f"Auto-import complete: {entry.name} — "
                f"{result['imported']} imported, {result['skipped']} skipped, {result['errors']} errors"
            )
            # Move to processed folder
            dest = os.path.join(_processed_dir, entry.name)
            # Handle name collision
            if os.path.exists(dest):
                base, suffix = os.path.splitext(entry.name)
                dest = os.path.join(_processed_dir, f"{base}_{int(time.time())}{suffix}")
            shutil.move(file_path, dest)
        except Exception as e:
            logger.error(f"Auto-import failed for {entry.name}: {e}")
            # Move to failed folder
            try:
                dest = os.path.join(_failed_dir, entry.name)
                if os.path.exists(dest):
                    base, suffix = os.path.splitext(entry.name)
                    dest = os.path.join(_failed_dir, f"{base}_{int(time.time())}{suffix}")
                shutil.move(file_path, dest)
            except Exception:
                pass


def _watcher_loop():
    """Background polling loop."""
    logger.info(f"Folder watcher started — monitoring: {WATCH_DIR} (poll every {POLL_INTERVAL}s)")
    _ensure_dirs()
    while True:
        try:
            _scan_and_import()
        except Exception as e:
            logger.error(f"Watcher error: {e}")
        time.sleep(POLL_INTERVAL)


def start_watcher():
    """Start the folder watcher in a background daemon thread."""
    thread = threading.Thread(target=_watcher_loop, daemon=True, name="folder-watcher")
    thread.start()
    return thread
