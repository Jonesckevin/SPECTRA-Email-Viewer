"""Forensics router: digital forensic analysis of emails + persistent scanning."""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File

from app.database import get_db
from app.dependencies import get_current_project
from app.services.forensics import (
    compute_hashes,
    compute_file_hash,
    parse_received_chain,
    extract_auth_results,
    detect_suspicious_indicators,
)

router = APIRouter(prefix="/api/emails", tags=["forensics"])


# ─── Persistent scanning ───

# Track cancel events for running scans so they can be force-stopped
_scan_cancel_events: dict[str, threading.Event] = {}
_scan_cancel_lock = threading.Lock()


def cleanup_stale_scans(project_slug: str = "default") -> None:
    """Mark any 'running' scan jobs as 'stopped' on startup (orphaned by restart)."""
    try:
        with get_db(project_slug) as conn:
            updated = conn.execute(
                "UPDATE scan_jobs SET status = 'stopped', completed_at = datetime('now') "
                "WHERE status = 'running'"
            ).rowcount
            if updated:
                import logging
                logging.getLogger(__name__).info("Marked %d orphaned scan job(s) as stopped", updated)
    except Exception:
        pass


@router.post("/scan/start")
def start_scan(project_slug: str = Depends(get_current_project)):
    """Start a background scan of all emails for suspicious indicators."""
    scan_id = uuid.uuid4().hex[:12]
    cancel_event = threading.Event()

    with _scan_cancel_lock:
        _scan_cancel_events[scan_id] = cancel_event

    with get_db(project_slug) as conn:
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        conn.execute(
            "INSERT INTO scan_jobs (id, status, total_emails) VALUES (?, 'running', ?)",
            (scan_id, total),
        )

    def _run_scan():
        try:
            from app.services.activity_log import log_activity
            log_activity("info", "scan", f"Scan started (id: {scan_id})", project=project_slug)
        except Exception:
            pass

        page_size = 200
        scanned = 0
        flagged = 0
        stopped = False

        try:
            with get_db(project_slug) as conn:
                while True:
                    if cancel_event.is_set():
                        stopped = True
                        break

                    rows = conn.execute(
                        "SELECT id, message_id, subject, sender, sender_name, recipients, raw_headers "
                        "FROM emails ORDER BY id LIMIT ? OFFSET ?",
                        (page_size, scanned),
                    ).fetchall()

                    if not rows:
                        break

                    for row in rows:
                        if cancel_event.is_set():
                            stopped = True
                            break

                        raw_headers = row["raw_headers"] or ""
                        email_data = {
                            "sender": row["sender"] or "",
                            "sender_name": row["sender_name"] or "",
                            "recipients": row["recipients"] or "",
                            "message_id": row["message_id"] or "",
                            "subject": row["subject"] or "",
                        }

                        received_chain = parse_received_chain(raw_headers)
                        indicators = detect_suspicious_indicators(email_data, raw_headers, received_chain)

                        # Also run YARA if rules loaded
                        try:
                            from app.services.yara_scanner import scan_email
                            yara_results = scan_email({
                                **email_data,
                                "body_text": "",
                                "body_html": "",
                                "raw_headers": raw_headers,
                            })
                            indicators.extend(yara_results)
                        except Exception:
                            pass

                        for ind in indicators:
                            conn.execute(
                                "INSERT INTO scan_results (scan_id, email_id, indicator_type, severity, message) "
                                "VALUES (?, ?, ?, ?, ?)",
                                (scan_id, row["id"], ind.get("rule", "heuristic"), ind["severity"], ind["message"]),
                            )
                            flagged += 1

                        scanned += 1

                    if stopped:
                        break

                    conn.execute(
                        "UPDATE scan_jobs SET scanned = ?, flagged = ? WHERE id = ?",
                        (scanned, flagged, scan_id),
                    )
                    conn.commit()

                final_status = "stopped" if stopped else "completed"
                conn.execute(
                    "UPDATE scan_jobs SET status = ?, scanned = ?, flagged = ?, "
                    "completed_at = datetime('now') WHERE id = ?",
                    (final_status, scanned, flagged, scan_id),
                )

            try:
                from app.services.activity_log import log_activity
                if stopped:
                    log_activity(
                        "warning", "scan",
                        f"Scan stopped: {scanned} scanned, {flagged} indicators found",
                        project=project_slug,
                        details={"scan_id": scan_id, "scanned": scanned, "flagged": flagged},
                    )
                else:
                    log_activity(
                        "info", "scan",
                        f"Scan complete: {scanned} scanned, {flagged} indicators found",
                        project=project_slug,
                        details={"scan_id": scan_id, "scanned": scanned, "flagged": flagged},
                    )
            except Exception:
                pass

        except Exception as e:
            try:
                with get_db(project_slug) as conn:
                    conn.execute(
                        "UPDATE scan_jobs SET status = 'failed', scanned = ?, flagged = ?, "
                        "completed_at = datetime('now') WHERE id = ?",
                        (scanned, flagged, scan_id),
                    )
            except Exception:
                pass

        finally:
            with _scan_cancel_lock:
                _scan_cancel_events.pop(scan_id, None)

    thread = threading.Thread(target=_run_scan, daemon=True, name=f"scan-{scan_id}")
    thread.start()

    return {"scan_id": scan_id, "total": total, "status": "running"}


@router.post("/scan/stop")
def stop_scan(project_slug: str = Depends(get_current_project)):
    """Force-stop the currently running scan."""
    with get_db(project_slug) as conn:
        job = conn.execute(
            "SELECT id FROM scan_jobs WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

    if not job:
        raise HTTPException(status_code=404, detail="No running scan found")

    scan_id = job["id"]
    with _scan_cancel_lock:
        cancel_event = _scan_cancel_events.get(scan_id)

    if cancel_event:
        cancel_event.set()
        return {"message": "Stop signal sent", "scan_id": scan_id}

    # No thread found (e.g. after container restart) — force-update DB directly
    with get_db(project_slug) as conn:
        conn.execute(
            "UPDATE scan_jobs SET status = 'stopped', completed_at = datetime('now') WHERE id = ?",
            (scan_id,),
        )
    return {"message": "Scan marked as stopped (thread was gone)", "scan_id": scan_id}


def _map_scan_status(db_status: str) -> str:
    """Map internal DB status values to API-facing status values."""
    return {"done": "completed", "error": "failed"}.get(db_status, db_status)


@router.get("/scan/status")
def get_scan_status(project_slug: str = Depends(get_current_project)):
    """Get the status of the most recent scan job."""
    with get_db(project_slug) as conn:
        job = conn.execute(
            "SELECT * FROM scan_jobs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

    if not job:
        return {"has_scan": False}

    return {
        "has_scan": True,
        "scan_id": job["id"],
        "status": _map_scan_status(job["status"]),
        "total": job["total_emails"],
        "processed": job["scanned"],
        "flagged": job["flagged"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
    }


@router.get("/scan/results")
def get_scan_results(
    scan_id: str | None = Query(None),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    project_slug: str = Depends(get_current_project),
):
    """Get scan results, optionally filtered."""
    offset = (page - 1) * per_page

    with get_db(project_slug) as conn:
        # Get the scan_id if not provided (use latest)
        if not scan_id:
            job = conn.execute("SELECT id FROM scan_jobs ORDER BY started_at DESC LIMIT 1").fetchone()
            if not job:
                return {"results": [], "total": 0}
            scan_id = job["id"]

        conditions = ["sr.scan_id = ?"]
        params: list = [scan_id]

        if severity:
            conditions.append("sr.severity = ?")
            params.append(severity)

        where = "WHERE " + " AND ".join(conditions)

        # Get distinct flagged emails with their indicators
        total_flagged = conn.execute(
            f"SELECT COUNT(DISTINCT sr.email_id) FROM scan_results sr {where}",
            params,
        ).fetchone()[0]

        flagged_ids = conn.execute(
            f"SELECT DISTINCT sr.email_id FROM scan_results sr {where} "
            f"ORDER BY sr.email_id LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()

        results = []
        for row in flagged_ids:
            eid = row["email_id"]
            email = conn.execute(
                "SELECT id, subject, sender, sender_name FROM emails WHERE id = ?",
                (eid,),
            ).fetchone()
            if not email:
                continue

            indicators = conn.execute(
                "SELECT severity, message FROM scan_results WHERE scan_id = ? AND email_id = ?",
                (scan_id, eid),
            ).fetchall()

            results.append({
                "email_id": eid,
                "subject": email["subject"] or "(no subject)",
                "sender": email["sender"] or "",
                "sender_name": email["sender_name"] or "",
                "indicators": [{"severity": i["severity"], "message": i["message"]} for i in indicators],
            })

    return {
        "results": results,
        "total": total_flagged,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total_flagged + per_page - 1) // per_page),
        "scan_id": scan_id,
    }


# ─── Legacy scan endpoint (kept for compatibility) ───

@router.get("/scan-suspicious")
def scan_all_suspicious(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    project_slug: str = Depends(get_current_project),
):
    """
    Scan emails in bulk for suspicious indicators.
    Returns only emails that have at least one indicator.
    """
    offset = (page - 1) * per_page

    with get_db(project_slug) as conn:
        rows = conn.execute(
            "SELECT id, message_id, subject, sender, sender_name, recipients, raw_headers "
            "FROM emails ORDER BY id LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]

    flagged = []
    for row in rows:
        raw_headers = row["raw_headers"] or ""
        email_data = {
            "sender": row["sender"] or "",
            "sender_name": row["sender_name"] or "",
            "recipients": row["recipients"] or "",
            "message_id": row["message_id"] or "",
            "subject": row["subject"] or "",
        }
        received_chain = parse_received_chain(raw_headers)
        indicators = detect_suspicious_indicators(email_data, raw_headers, received_chain)
        if indicators:
            flagged.append({
                "email_id": row["id"],
                "subject": row["subject"] or "(no subject)",
                "sender": row["sender"] or "",
                "sender_name": row["sender_name"] or "",
                "indicators": indicators,
            })

    return {
        "flagged": flagged,
        "scanned": len(rows),
        "total_emails": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


# ─── Per-email forensics ───

@router.get("/{email_id}/forensics")
def get_forensics(email_id: int, project_slug: str = Depends(get_current_project)):
    """
    Get comprehensive forensic analysis for an email.
    """
    with get_db(project_slug) as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Email not found")

        attachments = conn.execute(
            "SELECT id, filename, content_type, size, file_path FROM attachments WHERE email_id = ?",
            (email_id,),
        ).fetchall()

    raw_headers = row["raw_headers"] or ""
    email_data = {
        "sender": row["sender"] or "",
        "sender_name": row["sender_name"] or "",
        "recipients": row["recipients"] or "",
        "message_id": row["message_id"] or "",
        "subject": row["subject"] or "",
    }

    received_chain = parse_received_chain(raw_headers)
    auth_results = extract_auth_results(raw_headers)
    suspicious = detect_suspicious_indicators(email_data, raw_headers, received_chain)

    body_text = row["body_text"] or ""
    body_html = row["body_html"] or ""
    body_text_hashes = compute_hashes(body_text) if body_text else {}
    body_html_hashes = compute_hashes(body_html) if body_html else {}

    attachment_hashes = []
    for att in attachments:
        file_path = att["file_path"]
        h = compute_file_hash(file_path) if os.path.exists(file_path) else {"sha256": "", "error": "File not found"}
        attachment_hashes.append({
            "id": att["id"],
            "filename": att["filename"],
            "content_type": att["content_type"],
            "size": att["size"],
            "hashes": h,
        })

    return {
        "email_id": email_id,
        "metadata": {
            "message_id": row["message_id"] or "",
            "file_source": row["file_source"] or "",
            "imported_at": row["imported_at"] or "",
            "content_hash": row["content_hash"] or "",
        },
        "raw_headers": raw_headers,
        "has_forensic_data": bool(raw_headers),
        "received_chain": received_chain,
        "authentication": auth_results,
        "suspicious_indicators": suspicious,
        "content_hashes": {
            "body_text": body_text_hashes,
            "body_html": body_html_hashes,
        },
        "attachment_hashes": attachment_hashes,
    }


# ─── YARA endpoints ───

@router.post("/yara/upload")
async def upload_yara_rules(file: UploadFile = File(...)):
    """Upload a YARA rules file for the current session."""
    from app.services.yara_scanner import load_rules, is_available

    if not is_available():
        raise HTTPException(501, "YARA scanning is not available (yara-python not installed)")

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "YARA file too large (max 10MB)")

    try:
        result = load_rules(content, filename=file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        from app.services.activity_log import log_activity
        log_activity("info", "yara", f"YARA rules uploaded: {file.filename} ({result['rule_count']} rules)")
    except Exception:
        pass

    return result


@router.get("/yara/status")
def yara_status():
    """Get YARA rules status."""
    from app.services.yara_scanner import get_status, is_available
    status = get_status()
    status["available"] = is_available()
    return status


@router.delete("/yara")
def clear_yara():
    """Clear loaded YARA rules."""
    from app.services.yara_scanner import clear_rules
    clear_rules()
    return {"status": "ok"}
