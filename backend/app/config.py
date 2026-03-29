import os
from pathlib import Path

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/emails.db")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
WATCH_DIR = os.environ.get("WATCH_DIR", "watch")
PROJECTS_DIR = os.environ.get("PROJECTS_DIR", "data/projects")
WKHTMLTOIMAGE_PATH = os.environ.get("WKHTMLTOIMAGE_PATH", "/usr/local/bin/wkhtmltoimage-xvfb")

# Ensure directories exist
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(WATCH_DIR).mkdir(parents=True, exist_ok=True)
Path(PROJECTS_DIR).mkdir(parents=True, exist_ok=True)

SUPPORTED_FORMATS = {
    ".eml": "eml",
    ".msg": "msg",
    ".mbox": "mbox",
    ".pst": "pst",
    ".ost": "ost",
    ".olm": "olm",
    ".edb": "edb",
}

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB
