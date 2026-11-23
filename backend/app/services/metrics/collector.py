"""Background metrics collector.

Three loops share this lifecycle:

* the hardware sampler, which feeds the live in-memory buffer every few
  seconds and folds each minute into one persisted row;
* the task sampler, which scrapes the journal on its own schedule so history
  is recorded whether or not a UI is connected;
* the pruner, which enforces the retention windows on startup and hourly.

Every SQLite call is pushed onto a worker thread, so nothing here blocks the
event loop. A failing job never stops its loop, but it is logged: a warning on
the first failure, at most one more every FAILURE_LOG_INTERVAL_SECONDS while it
keeps failing, and a recovery message once it succeeds again.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime

import psutil

from app.config import settings
from app.services.hardware import get_gpu_info
from app.services.metrics.buffer import DataPoint, TimeSeriesBuffer
from app.services.metrics.store import MetricsStore
from app.services.metrics.task_history import task_history


def store() -> MetricsStore:
    """The live store, resolved late so a rebind is picked up everywhere."""
    return task_history.store


log = logging.getLogger(__name__)

FAILURE_LOG_INTERVAL_SECONDS = 600.0


class FailureLog:
    """Rate-limited warnings for a background job that keeps failing.

    Without this, an unwritable database stops the history silently: the
    loops have to swallow errors to keep running, so nothing else reports it.
    """

    def __init__(
        self,
        job: str,
        interval_seconds: float = FAILURE_LOG_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.job = job
        self.interval_seconds = interval_seconds
        self._clock = clock
        self.failures = 0
        self._last_logged: float | None = None

    def failed(self, error: BaseException) -> None:
        self.failures += 1
        now = self._clock()
        if self._last_logged is not None and now - self._last_logged < self.interval_seconds:
            return
        self._last_logged = now
        if self.failures == 1:
            log.warning("%s failed: %s", self.job, error, exc_info=error)
        else:
            log.warning(
                "%s still failing (%d failures so far): %s", self.job, self.failures, error
            )

    def succeeded(self) -> None:
        if self.failures:
            log.warning("%s recovered after %d failures", self.job, self.failures)
        self.reset()

    def reset(self) -> None:
        self.failures = 0
        self._last_logged = None


live_failures = FailureLog("Hardware sampling")
rollup_failures = FailureLog("Hardware history write")
task_sampler_failures = FailureLog("Task history sampling")
prune_failures = FailureLog("Metrics history pruning")
migration_failures = FailureLog("Import of task_history.json")
FAILURE_LOGS = (
    live_failures,
    rollup_failures,
    task_sampler_failures,
    prune_failures,
    migration_failures,
)

buffer = TimeSeriesBuffer(retention_minutes=30, interval_seconds=5)

_task: asyncio.Task | None = None
_task_sampler: asyncio.Task | None = None
_pruner: asyncio.Task | None = None
_subscribers: list[asyncio.Queue] = []


class _MinuteAggregate:
    """Running aggregate for the minute currently being sampled.

    The 5s buffer stays as it is for the live view; one downsampled row per
    minute is persisted. The row is upserted on every sample rather
    than written when the minute closes, and a new aggregate starts from the
    row already stored for its minute (see seed()), so a restart mid-minute
    keeps what was already observed.
    """

    _MEANS = ("ram_used_gb", "ram_total_gb", "ram_percent", "cpu_percent", "swap_used_gb")
    _OPTIONAL = ("gpu_load_percent", "gpu_temp_c", "gpu_vram_used_gb", "gpu_gtt_used_gb")

    def __init__(self, minute_start: datetime) -> None:
        self.minute_start = minute_start
        self.count = 0
        self._sums: dict[str, float] = {}
        # Optional metrics and sensors: [sum, number of samples that had one].
        self._optional: dict[str, list[float]] = {key: [0.0, 0] for key in self._OPTIONAL}
        self.ram_percent_min: float | None = None
        self.ram_percent_max: float | None = None
        self.temperatures: dict[str, list[float]] = {}

    def seed(self, row: dict) -> None:
        """Start from the stored row for this minute, written before a restart.

        The stored means are weighted by the stored sample count. An optional
        metric is taken to have been present in all of them.
        """
        count = int(row.get("sample_count") or 0)
        if count <= 0:
            return
        self.count = count
        for key in self._MEANS:
            if row.get(key) is not None:
                self._sums[key] = float(row[key]) * count
        for key in self._OPTIONAL:
            if row.get(key) is not None:
                self._optional[key] = [float(row[key]) * count, count]
        self.ram_percent_min = row.get("ram_percent_min")
        self.ram_percent_max = row.get("ram_percent_max")
        temperatures = row.get("temperatures") or {}
        if isinstance(temperatures, str):
            try:
                temperatures = json.loads(temperatures)
            except ValueError:
                temperatures = {}
        if isinstance(temperatures, dict):
            for label, value in temperatures.items():
                try:
                    self.temperatures[label] = [float(value) * count, count]
                except (TypeError, ValueError):
                    continue

    def add(self, point: DataPoint) -> None:
        self.count += 1
        for key in self._MEANS:
            self._sums[key] = self._sums.get(key, 0.0) + getattr(point, key)

        # A sensor or sysfs file that reads NaN or infinity once would spoil
        # the mean of its whole minute; that reading is left out instead.
        for key, total in self._optional.items():
            value = getattr(point, key)
            if value is not None and math.isfinite(value):
                total[0] += value
                total[1] += 1

        self.ram_percent_min = (
            point.ram_percent
            if self.ram_percent_min is None
            else min(self.ram_percent_min, point.ram_percent)
        )
        self.ram_percent_max = (
            point.ram_percent
            if self.ram_percent_max is None
            else max(self.ram_percent_max, point.ram_percent)
        )

        for label, value in point.temperatures.items():
            if not math.isfinite(value):
                continue
            total = self.temperatures.setdefault(label, [0.0, 0])
            total[0] += value
            total[1] += 1

    def as_row(self) -> dict:
        def mean(key: str) -> float:
            return round(self._sums.get(key, 0.0) / self.count, 3) if self.count else 0.0

        def optional_mean(key: str) -> float | None:
            total, samples = self._optional[key]
            return round(total / samples, 2) if samples else None

        return {
            "timestamp": self.minute_start.isoformat(),
            "sample_count": self.count,
            "ram_used_gb": mean("ram_used_gb"),
            "ram_total_gb": mean("ram_total_gb"),
            "ram_percent": mean("ram_percent"),
            "ram_percent_min": round(self.ram_percent_min or 0.0, 2),
            "ram_percent_max": round(self.ram_percent_max or 0.0, 2),
            "cpu_percent": mean("cpu_percent"),
            "swap_used_gb": mean("swap_used_gb"),
            "gpu_load_percent": optional_mean("gpu_load_percent"),
            "gpu_temp_c": optional_mean("gpu_temp_c"),
            "gpu_vram_used_gb": optional_mean("gpu_vram_used_gb"),
            "gpu_gtt_used_gb": optional_mean("gpu_gtt_used_gb"),
            "temperatures": {
                label: round(total / samples, 1)
                for label, (total, samples) in self.temperatures.items()
                if samples
            },
        }


_minute: _MinuteAggregate | None = None
_minute_lock = asyncio.Lock()


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
    # The live view first: a locked database can hold the write below for
    # up to the connection timeout, and the charts must not wait for it.
    for queue in _subscribers:
        try:
            queue.put_nowait(latest)
        except asyncio.QueueFull:
            pass
    try:
        await _persist_minute(point)
    except Exception as error:
        # Losing a rollup must never stop the live stream.
        rollup_failures.failed(error)
    return latest or {}


async def _persist_minute(point: DataPoint) -> None:
    """Fold one live sample into the persisted per-minute rollup."""
    global _minute
    minute_start = point.timestamp.astimezone(UTC).replace(second=0, microsecond=0)
    # The lock spans the write too: the endpoints can call collect_once()
    # alongside the loop, and an out-of-order upsert would drop a sample.
    async with _minute_lock:
        if _minute is None or _minute.minute_start != minute_start:
            _minute = _MinuteAggregate(minute_start)
            try:
                stored = await asyncio.to_thread(store().get_hardware_minute, minute_start)
            except Exception as error:
                # The upsert below reports a database that cannot be used.
                log.debug("Could not read the stored minute %s: %s", minute_start, error)
            else:
                if stored:
                    _minute.seed(stored)
        _minute.add(point)
        row = _minute.as_row()
        try:
            await asyncio.to_thread(store().upsert_hardware_minute, row)
        except Exception as error:
            # Losing a rollup must never stop the live stream.
            rollup_failures.failed(error)
        else:
            rollup_failures.succeeded()


async def sample_tasks_once() -> int:
    """Record every finished inference the journal still carries."""
    try:
        stored = await asyncio.to_thread(task_history.refresh_from_logs)
    except Exception as error:
        task_sampler_failures.failed(error)
        return 0
    task_sampler_failures.succeeded()
    return stored


async def prune_once() -> dict[str, int]:
    """Apply both retention windows."""
    try:
        removed = await asyncio.to_thread(
            store().prune,
            settings.task_retention_days,
            settings.hardware_retention_days,
        )
    except Exception as error:
        prune_failures.failed(error)
        return {"tasks": 0, "hardware": 0}
    prune_failures.succeeded()
    return removed


async def _collector_loop(interval_seconds: int) -> None:
    loop = asyncio.get_running_loop()
    while True:
        started = loop.time()
        try:
            await collect_once()
        except Exception as error:
            live_failures.failed(error)
        else:
            live_failures.succeeded()
        # Counted from the start of the sample, so a slow write to the
        # history does not space out the live points.
        await asyncio.sleep(max(0.0, interval_seconds - (loop.time() - started)))


async def _task_sampler_loop(interval_seconds: int) -> None:
    # The import runs here, before the first sample, rather than as a task of
    # its own: that one sampled too, at the same moment as this loop's first
    # tick, and stop_collector() could not cancel it.
    await import_legacy_history()
    while True:
        try:
            await sample_tasks_once()
        except Exception as error:
            task_sampler_failures.failed(error)
        await asyncio.sleep(interval_seconds)


async def _pruner_loop(interval_seconds: int) -> None:
    while True:
        try:
            await prune_once()
        except Exception as error:
            prune_failures.failed(error)
        await asyncio.sleep(interval_seconds)


async def import_legacy_history() -> None:
    """Import the pre-SQLite JSON history, once per start.

    A failed import is logged and left unmarked, so the next start tries it
    again; it is not retried while this process runs.
    """
    try:
        await asyncio.to_thread(task_history.migrate_legacy_json)
    except Exception as error:
        migration_failures.failed(error)


def start_collector(interval_seconds: int = 5) -> None:
    global _task, _task_sampler, _pruner

    if _task is None or _task.done():
        _task = asyncio.create_task(_collector_loop(interval_seconds))
    if _task_sampler is None or _task_sampler.done():
        _task_sampler = asyncio.create_task(
            _task_sampler_loop(max(1, settings.task_sampler_interval_seconds))
        )
    if _pruner is None or _pruner.done():
        _pruner = asyncio.create_task(
            _pruner_loop(max(60, settings.metrics_prune_interval_seconds))
        )


def stop_collector() -> None:
    global _task, _task_sampler, _pruner
    for running in (_task, _task_sampler, _pruner):
        if running and not running.done():
            running.cancel()
    _task = None
    _task_sampler = None
    _pruner = None


def _sample() -> DataPoint:
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    gpu_info = get_gpu_info()
    temperatures: dict[str, float] = {}
    try:
        for chip_name, entries in psutil.sensors_temperatures().items():
            for entry in entries:
                label = f"{chip_name}/{entry.label or 'sensor'}"
                temperatures[label] = entry.current
    except Exception:
        pass

    return DataPoint(
        timestamp=datetime.now(UTC),
        ram_used_gb=memory.used / (1024**3),
        ram_total_gb=memory.total / (1024**3),
        ram_percent=memory.percent,
        cpu_percent=psutil.cpu_percent(interval=0),
        swap_used_gb=swap.used / (1024**3),
        gpu_load_percent=gpu_info["gpu_load_percent"],
        gpu_temp_c=gpu_info["gpu_temp_c"],
        gpu_vram_used_gb=gpu_info["gpu_vram_used_gb"],
        gpu_gtt_used_gb=gpu_info["gpu_gtt_used_gb"],
        temperatures=temperatures,
    )
