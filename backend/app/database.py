import sqlite3
import threading
from contextlib import contextmanager

from app.config import PROJECTS_DIR
from app.services.projects import get_active_project, get_project_db_path

_local = threading.local()


def get_connection(project_slug: str | None = None) -> sqlite3.Connection:
    slug = project_slug or get_active_project()
    if not hasattr(_local, "connections"):
        _local.connections = {}

    conn = _local.connections.get(slug)
    if conn is None:
        db_path = get_project_db_path(slug)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.connections[slug] = conn
    return conn


@contextmanager
def get_db(project_slug: str | None = None):
    conn = get_connection(project_slug)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_project_connections(project_slug: str | None = None):
    """Close thread-local connections for a project (or all projects)."""
    if not hasattr(_local, "connections"):
        return
    if project_slug:
        conn = _local.connections.pop(project_slug, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    else:
        for conn in _local.connections.values():
            try:
                conn.close()
            except Exception:
                pass
        _local.connections.clear()


def init_db(project_slug: str | None = None):
    slug = project_slug or "default"
    db_path = get_project_db_path(slug)

    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_source TEXT NOT NULL,
            message_id TEXT,
            subject TEXT DEFAULT '',
            sender TEXT DEFAULT '',
            sender_name TEXT DEFAULT '',
            recipients TEXT DEFAULT '',
            cc TEXT DEFAULT '',
            bcc TEXT DEFAULT '',
            date TEXT,
            date_unix REAL,
            body_text TEXT DEFAULT '',
            body_html TEXT DEFAULT '',
            has_attachments INTEGER DEFAULT 0,
            is_starred INTEGER DEFAULT 0,
            imported_at TEXT DEFAULT (datetime('now')),
            raw_headers TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            UNIQUE(message_id, file_source)
        );

        CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date_unix);
        CREATE INDEX IF NOT EXISTS idx_emails_starred ON emails(is_starred);
        CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);
        CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT DEFAULT '',
            size INTEGER DEFAULT 0,
            file_path TEXT NOT NULL,
            FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments(email_id);

        CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
            subject,
            sender,
            sender_name,
            recipients,
            body_text,
            content='emails',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        );

        -- Triggers to keep FTS index in sync
        CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
            INSERT INTO emails_fts(rowid, subject, sender, sender_name, recipients, body_text)
            VALUES (new.id, new.subject, new.sender, new.sender_name, new.recipients, new.body_text);
        END;

        CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, subject, sender, sender_name, recipients, body_text)
            VALUES ('delete', old.id, old.subject, old.sender, old.sender_name, old.recipients, old.body_text);
        END;

        CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, subject, sender, sender_name, recipients, body_text)
            VALUES ('delete', old.id, old.subject, old.sender, old.sender_name, old.recipients, old.body_text);
            INSERT INTO emails_fts(rowid, subject, sender, sender_name, recipients, body_text)
            VALUES (new.id, new.subject, new.sender, new.sender_name, new.recipients, new.body_text);
        END;

        -- Scan results table for persistent scanner state
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT NOT NULL,
            email_id INTEGER NOT NULL,
            indicator_type TEXT DEFAULT '',
            severity TEXT DEFAULT '',
            message TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_scan_results_scan ON scan_results(scan_id);
        CREATE INDEX IF NOT EXISTS idx_scan_results_email ON scan_results(email_id);

        -- Scan jobs table
        CREATE TABLE IF NOT EXISTS scan_jobs (
            id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'running',
            total_emails INTEGER DEFAULT 0,
            scanned INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
    """)
    conn.commit()

    # Migrate existing databases: add new columns if missing
    for col, default in [("raw_headers", "''"), ("content_hash", "''")]:
        try:
            conn.execute(f"ALTER TABLE emails ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
        except Exception:
            pass  # Column already exists

    conn.close()
