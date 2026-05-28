"""Thread-safe circular time-series metrics buffer."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class DataPoint:
    timestamp: datetime
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    cpu_percent: float
    swap_used_gb: float
    gpu_load_percent: float | None = None
    gpu_temp_c: float | None = None
    temperatures: dict[str, float] = field(default_factory=dict)


class TimeSeriesBuffer:
    def __init__(self, retention_minutes: int = 30, interval_seconds: int = 5) -> None:
        self.retention = timedelta(minutes=retention_minutes)
        self.interval_seconds = interval_seconds
        self.capacity = (retention_minutes * 60) // interval_seconds
        self._buffer: deque[DataPoint] = deque(maxlen=self.capacity)
        self._lock = threading.Lock()

    def append(self, point: DataPoint) -> None:
        with self._lock:
            self._buffer.append(point)

    def get_range(self, minutes: int | None = None) -> list[dict]:
        with self._lock:
            points = list(self._buffer)

        if minutes:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            points = [point for point in points if self._aware_timestamp(point.timestamp) >= cutoff]

        return [self._serialize(point) for point in points]

    def get_latest(self) -> dict | None:
        with self._lock:
            if not self._buffer:
                return None
            return self._serialize(self._buffer[-1])

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def _serialize(self, point: DataPoint) -> dict:
        return {
            "t": self._aware_timestamp(point.timestamp).isoformat(),
            "ram_used": round(point.ram_used_gb, 2),
            "ram_total": round(point.ram_total_gb, 2),
            "ram_pct": round(point.ram_percent, 1),
            "cpu_pct": round(point.cpu_percent, 1),
            "swap_used": round(point.swap_used_gb, 2),
            "gpu_load_pct": round(point.gpu_load_percent, 1) if point.gpu_load_percent is not None else None,
            "gpu_temp_c": round(point.gpu_temp_c, 1) if point.gpu_temp_c is not None else None,
            "temps": {key: round(value, 1) for key, value in point.temperatures.items()},
        }

    def _aware_timestamp(self, timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)
