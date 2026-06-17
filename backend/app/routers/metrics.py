"""Metrics endpoints and WebSocket stream."""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from app.services.metrics.collector import buffer, collect_once, subscribe, unsubscribe
from app.services.metrics.task_history import TaskHistory
from app.services.security import auth_required_for_host, key_configured, key_from_websocket, verify_key

router = APIRouter(prefix="/api/metrics", tags=["metrics"])
ws_router = APIRouter()
task_history = TaskHistory()


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
async def get_tasks(n: int = Query(default=20, ge=1, le=50)):
    return {"tasks": task_history.get_recent(n)}


@router.get("/tasks/csv")
async def export_tasks_csv():
    return PlainTextResponse(
        task_history.export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lcc-tasks.csv"},
    )


@router.post("/clear")
async def clear_metrics():
    buffer.clear()
    task_history.clear()
    return {"cleared": True}


@ws_router.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    host = websocket.client.host if websocket.client else None
    if auth_required_for_host(host):
        if not key_configured() or not verify_key(key_from_websocket(websocket)):
            await websocket.close(code=1008)
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
