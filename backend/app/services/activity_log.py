"""
Activity logging service.
Uses a shared activity.db across all projects for cross-project log visibility.
Provides structured logging with categories and SSE streaming support.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.config import PROJECTS_DIR

logger = logging.getLogger(__name__)

_ACTIVITY_DB_PATH = os.path.join(os.path.dirname(PROJECTS_DIR), "activity.db")
_local = threading.local()
_listeners: list = []
_listeners_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "activity_conn") or _local.activity_conn is None:
        os.makedirs(os.path.dirname(_ACTIVITY_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(_ACTIVITY_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.activity_conn = conn
    return _local.activity_conn


@contextmanager
def _get_db():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_activity_db():
    """Initialize the activity log database."""
    os.makedirs(os.path.dirname(_ACTIVITY_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_ACTIVITY_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            level TEXT DEFAULT 'info',
            category TEXT DEFAULT 'system',
            project TEXT DEFAULT '',
            message TEXT NOT NULL,
            details TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_activity_cat ON activity_log(category);
        CREATE INDEX IF NOT EXISTS idx_activity_proj ON activity_log(project);
    """)
    conn.commit()
    conn.close()


def log_activity(
    level: str,
    category: str,
    message: str,
    project: str = "",
    details: Any = None,
) -> int:
    """
    Log an activity entry.
    Categories: import, scan, export, project, yara, system
    Levels: info, warning, error, success
    """
    details_str = json.dumps(details) if details else ""
    try:
        with _get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO activity_log (level, category, project, message, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (level, category, project, message, details_str),
            )
            log_id = cursor.lastrowid

        # Notify SSE listeners
        entry = {
            "id": log_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "category": category,
            "project": project,
            "message": message,
            "details": details_str,
        }
        _notify_listeners(entry)

        return log_id
    except Exception as e:
        logger.warning(f"Failed to log activity: {e}")
        return 0


def get_logs(
    limit: int = 100,
    offset: int = 0,
    category: str | None = None,
    level: str | None = None,
    project: str | None = None,
    since_id: int | None = None,
) -> dict:
    """Query activity logs with filters."""
    conditions = []
    params: list = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if level:
        conditions.append("level = ?")
        params.append(level)
    if project:
        conditions.append("project = ?")
        params.append(project)
    if since_id:
        conditions.append("id > ?")
        params.append(since_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with _get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM activity_log {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM activity_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return {
        "logs": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def clear_logs(before_id: int | None = None) -> int:
    """Clear activity logs. If before_id is given, only clear entries with id <= before_id."""
    with _get_db() as conn:
        if before_id:
            cursor = conn.execute("DELETE FROM activity_log WHERE id <= ?", (before_id,))
        else:
            cursor = conn.execute("DELETE FROM activity_log")
        return cursor.rowcount


def subscribe():
    """Subscribe to live log events. Returns a queue-like object."""
    import queue
    q: queue.Queue = queue.Queue()
    with _listeners_lock:
        _listeners.append(q)
    return q


def unsubscribe(q):
    """Unsubscribe from live log events."""
    with _listeners_lock:
        try:
            _listeners.remove(q)
        except ValueError:
            pass


def _notify_listeners(entry: dict):
    """Push a log entry to all SSE listeners."""
    with _listeners_lock:
        dead = []
        for q in _listeners:
            try:
                q.put_nowait(entry)
            except Exception:
                dead.append(q)
        for q in dead:
            try:
                _listeners.remove(q)
            except ValueError:
                pass
