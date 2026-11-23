"""
Log viewing and streaming router.

Provides:
- Recent logs (parsed)
- Last task stats
- WebSocket live streaming
"""
import asyncio
import contextlib

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.capabilities import capabilities
from app.models.schemas import LastTaskStats, RecentLogsResponse
from app.services.log_parser import _parse_log_line, get_recent_logs, parse_last_task
from app.services.security import authorize_websocket

router = APIRouter(prefix="/api/logs", tags=["logs"])

LOG_STREAM_COMMAND = [
    "journalctl", "-u", "lemond.service", "-f", "-o", "cat", "--no-pager", "-n", "0",
]
MAX_LOG_LINE_BYTES = 1024 * 1024
STOP_TIMEOUT_SECONDS = 5


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
    if not await authorize_websocket(websocket):
        return
    await websocket.accept()

    if not capabilities.cmd_journalctl:
        await websocket.send_json({
            "type": "error",
            "message": "journalctl not available"
        })
        await websocket.close()
        return

    process = None
    tasks: list[asyncio.Task] = []
    try:
        process = await asyncio.create_subprocess_exec(
            *LOG_STREAM_COMMAND,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=MAX_LOG_LINE_BYTES,
        )

        await websocket.send_json({"type": "connected", "message": "Log streaming started"})

        # Lemonade can stay silent for hours: waiting for a line must not hide
        # that the client is gone, or that LCC is shutting down.
        tasks = [
            asyncio.create_task(_forward_log_lines(process.stdout, websocket)),
            asyncio.create_task(_wait_for_disconnect(websocket)),
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        for task in tasks:
            task.cancel()
        if process:
            await _stop(process)
        await asyncio.gather(*tasks, return_exceptions=True)


async def _forward_log_lines(stdout: asyncio.StreamReader, websocket: WebSocket) -> None:
    while True:
        try:
            raw = await stdout.readline()
        except ValueError:  # longer than MAX_LOG_LINE_BYTES: the reader drops it
            continue
        if not raw:
            await websocket.send_json({"type": "ended", "message": "Log stream ended"})
            return
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            await websocket.send_json({
                "type": "log",
                "entry": _parse_log_line(line).model_dump()
            })


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass


async def _stop(process: asyncio.subprocess.Process) -> None:
    """End the process, even when this handler is being cancelled."""
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        process.terminate()
    with contextlib.suppress(TimeoutError):
        try:
            await asyncio.wait_for(process.wait(), timeout=STOP_TIMEOUT_SECONDS)
        finally:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
