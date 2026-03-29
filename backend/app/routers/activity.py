"""Activity log router: query logs and SSE streaming."""
from __future__ import annotations

import json
import queue

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.activity_log import get_logs, clear_logs, subscribe, unsubscribe

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
def query_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    category: str | None = Query(None),
    level: str | None = Query(None),
    project: str | None = Query(None),
    since_id: int | None = Query(None),
):
    """Query activity logs with filters."""
    return get_logs(
        limit=limit,
        offset=offset,
        category=category,
        level=level,
        project=project,
        since_id=since_id,
    )


@router.delete("")
def delete_logs(before_id: int | None = Query(None)):
    """Clear activity logs."""
    count = clear_logs(before_id=before_id)
    return {"deleted": count}


@router.get("/stream")
def stream_logs():
    """Server-Sent Events endpoint for live log streaming."""
    q = subscribe()

    def event_generator():
        try:
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    entry = q.get(timeout=30)
                    yield f"data: {json.dumps(entry)}\n\n"
                except queue.Empty:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
