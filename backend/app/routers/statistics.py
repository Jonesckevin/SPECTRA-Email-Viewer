"""Statistics router: aggregate analytics and charts data."""
from __future__ import annotations

from fastapi import APIRouter, Query, Depends

from app.database import get_db
from app.dependencies import get_current_project

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("")
def get_statistics(project_slug: str = Depends(get_current_project)):
    """
    Return comprehensive statistics for the email dataset.
    Includes top senders, domains, time distribution, etc.
    """
    with get_db(project_slug) as conn:
        # Total counts
        total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        starred = conn.execute("SELECT COUNT(*) FROM emails WHERE is_starred = 1").fetchone()[0]
        with_attachments = conn.execute("SELECT COUNT(*) FROM emails WHERE has_attachments = 1").fetchone()[0]
        total_attachments = conn.execute("SELECT COUNT(*) FROM attachments").fetchone()[0]

        # Top 10 senders by email count
        top_senders = [
            {"sender": r[0] or "(unknown)", "sender_name": r[1] or "", "count": r[2]}
            for r in conn.execute(
                "SELECT sender, sender_name, COUNT(*) as cnt "
                "FROM emails GROUP BY sender ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
        ]

        # Top 10 sender domains
        top_domains = [
            {"domain": r[0] or "(unknown)", "count": r[1]}
            for r in conn.execute(
                "SELECT CASE WHEN INSTR(sender, '@') > 0 "
                "  THEN LOWER(SUBSTR(sender, INSTR(sender, '@') + 1)) "
                "  ELSE '(no domain)' END as domain, "
                "COUNT(*) as cnt "
                "FROM emails GROUP BY domain ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
        ]

        # Top 10 recipients
        top_recipients = [
            {"recipient": r[0] or "(unknown)", "count": r[1]}
            for r in conn.execute(
                "SELECT recipients, COUNT(*) as cnt "
                "FROM emails GROUP BY recipients ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
        ]

        # Emails per month (using date_unix)
        emails_by_month = [
            {"month": r[0], "count": r[1]}
            for r in conn.execute(
                "SELECT strftime('%Y-%m', date_unix, 'unixepoch') as month, COUNT(*) as cnt "
                "FROM emails WHERE date_unix IS NOT NULL AND date_unix > 0 "
                "GROUP BY month ORDER BY month"
            ).fetchall()
        ]

        # Emails per day of week (0=Sunday..6=Saturday)
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        emails_by_day = [
            {"day": day_names[r[0]], "day_num": r[0], "count": r[1]}
            for r in conn.execute(
                "SELECT CAST(strftime('%w', date_unix, 'unixepoch') AS INTEGER) as dow, COUNT(*) as cnt "
                "FROM emails WHERE date_unix IS NOT NULL AND date_unix > 0 "
                "GROUP BY dow ORDER BY dow"
            ).fetchall()
        ]

        # Emails per hour of day
        emails_by_hour = [
            {"hour": r[0], "count": r[1]}
            for r in conn.execute(
                "SELECT CAST(strftime('%H', date_unix, 'unixepoch') AS INTEGER) as hr, COUNT(*) as cnt "
                "FROM emails WHERE date_unix IS NOT NULL AND date_unix > 0 "
                "GROUP BY hr ORDER BY hr"
            ).fetchall()
        ]

        # Top 10 attachment types
        top_attachment_types = [
            {"content_type": r[0] or "(unknown)", "count": r[1]}
            for r in conn.execute(
                "SELECT content_type, COUNT(*) as cnt "
                "FROM attachments GROUP BY content_type ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
        ]

        # Top 10 file sources
        top_sources = [
            {"source": r[0] or "(unknown)", "count": r[1]}
            for r in conn.execute(
                "SELECT file_source, COUNT(*) as cnt "
                "FROM emails GROUP BY file_source ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
        ]

        # Average email body size
        avg_body = conn.execute(
            "SELECT AVG(LENGTH(body_text) + LENGTH(body_html)) FROM emails"
        ).fetchone()[0] or 0

        # Date range
        date_range = conn.execute(
            "SELECT MIN(date), MAX(date) FROM emails WHERE date IS NOT NULL AND date != ''"
        ).fetchone()

    return {
        "overview": {
            "total_emails": total,
            "starred": starred,
            "with_attachments": with_attachments,
            "total_attachments": total_attachments,
            "avg_body_size": round(avg_body),
            "date_range": {
                "earliest": date_range[0] if date_range else None,
                "latest": date_range[1] if date_range else None,
            },
        },
        "top_senders": top_senders,
        "top_domains": top_domains,
        "top_recipients": top_recipients,
        "top_sources": top_sources,
        "top_attachment_types": top_attachment_types,
        "emails_by_month": emails_by_month,
        "emails_by_day": emails_by_day,
        "emails_by_hour": emails_by_hour,
    }
