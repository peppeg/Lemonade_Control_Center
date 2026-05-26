"""
Log viewing and streaming router.

Provides:
- Recent logs (parsed)
- Last task stats
- WebSocket live streaming
"""
import asyncio
import subprocess

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.capabilities import capabilities
from app.models.schemas import RecentLogsResponse, LastTaskStats
from app.services.log_parser import get_recent_logs, parse_last_task

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/recent", response_model=RecentLogsResponse)
async def recent_logs(n: int = Query(default=100, ge=10, le=500)):
    """Get recent parsed log entries from journalctl."""
    if not capabilities.cmd_journalctl:
        return RecentLogsResponse(entries=[], total_lines=0, source="unavailable")
    return get_recent_logs(n_lines=n)


@router.get("/last-task", response_model=LastTaskStats)
async def last_task_stats(max_tokens: int | None = Query(default=None)):
    """Parse the last completed task from logs."""
    if not capabilities.cmd_journalctl:
        return LastTaskStats(available=False)
    return parse_last_task(configured_max_tokens=max_tokens)


@router.websocket("/ws/logs")
async def stream_logs(websocket: WebSocket):
    """WebSocket endpoint for live log streaming."""
    await websocket.accept()

    if not capabilities.cmd_journalctl:
        await websocket.send_json({
            "type": "error",
            "message": "journalctl not available"
        })
        await websocket.close()
        return

    process = None
    try:
        process = subprocess.Popen(
            ["journalctl", "-u", "lemond.service", "-f", "-o", "cat",
             "--no-pager", "-n", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        await websocket.send_json({"type": "connected", "message": "Log streaming started"})

        loop = asyncio.get_event_loop()

        while True:
            line = await loop.run_in_executor(None, process.stdout.readline)

            if not line:
                await websocket.send_json({"type": "ended", "message": "Log stream ended"})
                break

            line = line.strip()
            if line:
                from app.services.log_parser import _parse_log_line
                entry = _parse_log_line(line)
                await websocket.send_json({
                    "type": "log",
                    "entry": entry.model_dump()
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
