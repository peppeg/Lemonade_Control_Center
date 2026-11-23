"""Metrics endpoints and WebSocket stream."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.services.metrics.collector import buffer, collect_once, subscribe, unsubscribe
from app.services.metrics.store import RANGE_WINDOWS, resolve_range
from app.services.metrics.task_history import TaskHistory, task_history
from app.services.security import authorize_websocket

router = APIRouter(prefix="/api/metrics", tags=["metrics"])
ws_router = APIRouter()

# Exported for callers that used to reach the history through this module.
__all__ = ["TaskHistory", "router", "task_history", "ws_router"]


@router.get("/history")
async def get_history(minutes: int = Query(default=30, ge=1, le=60)):
    if buffer.size == 0:
        await collect_once()
    return {"points": buffer.get_range(minutes), "total": buffer.size, "retention_minutes": 30}


@router.get("/latest")
async def get_latest():
    if buffer.size == 0:
        await collect_once()
    return {"point": buffer.get_latest()}


@router.get("/tasks")
async def get_tasks(
    n: int = Query(default=20, ge=1, le=5000),
    since: str | None = Query(default=None, description="ISO-8601 lower bound, inclusive"),
    until: str | None = Query(default=None, description="ISO-8601 upper bound, inclusive"),
):
    """Recent task records, oldest first.

    The response shape and the default of 20 records are unchanged; `since`
    and `until` narrow the window, and `n` reaches up to 5000 instead of 50.
    """
    window_start = _parse_boundary(since, "since")
    window_end = _parse_boundary(until, "until")
    tasks = await asyncio.to_thread(
        task_history.get_recent, n, window_start, window_end, True
    )
    return {"tasks": tasks}


@router.get("/tasks/series")
async def get_tasks_series(
    range: str = Query(default="24h", description="|".join(RANGE_WINDOWS)),
):
    """Time-bucketed generation-speed aggregates over a long window."""
    key, window, bucket_seconds = _resolve_range(range)
    end = datetime.now(UTC)
    start = end - window
    window = await asyncio.to_thread(task_history.window, start, end, bucket_seconds)
    return {
        "range": key,
        "bucket_seconds": bucket_seconds,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "buckets": window["buckets"],
        "summary": window["summary"],
    }


@router.get("/tasks/scale")
async def get_tasks_scale(
    range: str = Query(default="30d", description="|".join(RANGE_WINDOWS)),
    quantile: float = Query(default=0.95, gt=0.0, le=1.0),
):
    """One percentile of output_tokens over a window.

    The scatter sizes each mark against a fixed ceiling. Computing it in the
    browser meant downloading every run in the window just to reduce it to a
    single number; the store reads one column and reduces it here instead.
    """
    key, window, _bucket_seconds = _resolve_range(range)
    end = datetime.now(UTC)
    start = end - window
    result = await asyncio.to_thread(
        task_history.store.output_token_percentile, start, end, quantile
    )
    return {
        "range": key,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "quantile": quantile,
        "output_tokens": result["value"],
        "count": result["count"],
    }


@router.get("/hardware/series")
async def get_hardware_series(
    range: str = Query(default="24h", description="|".join(RANGE_WINDOWS)),
):
    """Time-bucketed hardware aggregates from the persisted per-minute rows."""
    key, window, bucket_seconds = _resolve_range(range)
    end = datetime.now(UTC)
    start = end - window
    buckets = await asyncio.to_thread(
        task_history.store.hardware_series, start, end, bucket_seconds
    )
    return {
        "range": key,
        "bucket_seconds": bucket_seconds,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "buckets": buckets,
    }


@router.get("/tasks/csv")
async def export_tasks_csv(
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    range: str | None = Query(default=None),
):
    """CSV export, optionally narrowed by the same window the charts use."""
    window_start = _parse_boundary(since, "since")
    window_end = _parse_boundary(until, "until")
    if range:
        _, window, _bucket = _resolve_range(range)
        if window_start is None:
            window_start = datetime.now(UTC) - window

    # Streamed: Starlette runs the synchronous generator in its thread pool, so
    # the journal refresh and the batched reads stay off the event loop.
    return StreamingResponse(
        task_history.export_csv(window_start, window_end, True),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lcc-tasks.csv"},
    )


# What each scope is allowed to destroy. "buffer" is the in-memory ring the
# live view streams into and refills within seconds; "history" additionally
# drops both SQLite tables, which is irreversible.
CLEAR_SCOPES = ("buffer", "history")


@router.get("/history/summary")
async def get_history_summary():
    """Row counts and oldest record per table.

    Read before the delete-history confirmation so the prompt can name what it
    is about to destroy instead of describing it vaguely.
    """
    return await asyncio.to_thread(task_history.store.history_summary)


@router.post("/clear")
async def clear_metrics(
    scope: str | None = Query(
        default=None, description="|".join(CLEAR_SCOPES)
    ),
):
    """Clear metrics at an explicit scope.

    There is deliberately no default. This endpoint used to wipe the whole
    persisted history under a one-word "Clear" button; an omitted or unknown
    scope is now a rejection, so no caller can destroy weeks of records by
    saying nothing.
    """
    if scope not in CLEAR_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"scope is required and must be one of: {', '.join(CLEAR_SCOPES)}",
        )

    buffer.clear()
    if scope == "buffer":
        return {"cleared": True, "scope": "buffer"}

    deleted = await asyncio.to_thread(task_history.clear)
    return {"cleared": True, "scope": "history", "deleted": deleted}


def _resolve_range(value: str | None) -> tuple[str, timedelta, int]:
    try:
        return resolve_range(value)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _parse_boundary(value: str | None, field: str) -> datetime | None:
    """Parse an ISO-8601 query bound, defaulting a naive value to UTC."""
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        # Converting a date at the edge of the calendar, such as year 1 with a
        # positive offset, overflows; it is a bad bound, not a server error.
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        raise HTTPException(
            status_code=400, detail=f"{field} must be an ISO-8601 timestamp"
        ) from None


@ws_router.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    if not await authorize_websocket(websocket):
        return

    await websocket.accept()
    queue = subscribe()
    try:
        while True:
            data = await queue.get()
            await websocket.send_json({"type": "metric", "data": data})
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(queue)
