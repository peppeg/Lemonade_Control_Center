"""Warnings for a problem that recurs, at most one per interval.

A record that cannot be read is met again on every read that still covers it,
every few seconds. Each is worth reporting, but not each time.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

DEFAULT_INTERVAL_SECONDS = 600.0


class RateLimitedWarning:
    """Log a warning at most once per interval, counting the ones held back."""

    def __init__(
        self,
        logger: logging.Logger,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._logger = logger
        self.interval_seconds = interval_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._last: float | None = None
        self._held = 0

    def warn(self, message: str, *args: object) -> bool:
        """Log `message % args` unless one was logged within the interval.

        Returns whether it was logged. The next one logged says how many were
        held back since the previous.
        """
        with self._lock:
            now = self._clock()
            if self._last is not None and now - self._last < self.interval_seconds:
                self._held += 1
                return False
            held, self._held, self._last = self._held, 0, now
        if held:
            message += " (and %d more like it since the last warning)"
            args = (*args, held)
        self._logger.warning(message, *args)
        return True

    def reset(self) -> None:
        with self._lock:
            self._last = None
            self._held = 0
