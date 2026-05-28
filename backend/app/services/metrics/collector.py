"""Background metrics collector."""
from __future__ import annotations

import asyncio
from datetime import datetime

import psutil

from app.services.metrics.buffer import DataPoint, TimeSeriesBuffer

buffer = TimeSeriesBuffer(retention_minutes=30, interval_seconds=5)
_task: asyncio.Task | None = None
_subscribers: list[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.append(queue)
    latest = buffer.get_latest()
    if latest is not None:
        queue.put_nowait(latest)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    if queue in _subscribers:
        _subscribers.remove(queue)


async def collect_once() -> dict:
    point = _sample()
    buffer.append(point)
    latest = buffer.get_latest()
    for queue in list(_subscribers):
        try:
            queue.put_nowait(latest)
        except asyncio.QueueFull:
            pass
    return latest or {}


async def _collector_loop(interval_seconds: int) -> None:
    while True:
        try:
            await collect_once()
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


def start_collector(interval_seconds: int = 5) -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_collector_loop(interval_seconds))


def stop_collector() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None


def _sample() -> DataPoint:
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    temperatures: dict[str, float] = {}
    try:
        for chip_name, entries in psutil.sensors_temperatures().items():
            for entry in entries:
                label = f"{chip_name}/{entry.label or 'sensor'}"
                temperatures[label] = entry.current
    except Exception:
        pass

    return DataPoint(
        timestamp=datetime.utcnow(),
        ram_used_gb=memory.used / (1024**3),
        ram_total_gb=memory.total / (1024**3),
        ram_percent=memory.percent,
        cpu_percent=psutil.cpu_percent(interval=0),
        swap_used_gb=swap.used / (1024**3),
        temperatures=temperatures,
    )
