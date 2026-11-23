"""SQLite-backed long-run store for task and hardware performance history.

The in-memory buffers elsewhere in this package answer the live view; this
module answers "what did generation speed look like last week". Two tables,
one row per completed inference and one aggregated row per minute of hardware
sampling. Hardware rows are pruned after 30 days by default; task rows are
kept unless a retention window is configured.

Plain stdlib sqlite3, no ORM. Every method is synchronous and short; callers
running inside the event loop push them through asyncio.to_thread.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import sqlite3
import stat
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import settings
from app.services.state_files import PRIVATE_FILE_MODE, ensure_private_dir

SCHEMA_VERSION = 1

# Bucket width per selectable range. Sized so that a bucket is usually
# populated rather than merely to cap the point count: empty buckets are
# dropped and gaps are drawn as gaps, so too fine a bucket turns a sparse
# workload into scattered points instead of a trend. Each range lands at
# 12-30 points, which the SVG charts render comfortably.
RANGE_WINDOWS: dict[str, tuple[timedelta, int]] = {
    "1h": (timedelta(hours=1), 5 * 60),
    "24h": (timedelta(hours=24), 60 * 60),
    "7d": (timedelta(days=7), 6 * 60 * 60),
    "30d": (timedelta(days=30), 24 * 60 * 60),
}

DEFAULT_RANGE = "24h"

# metrics_meta key holding when the history was last cleared, as an ISO-8601
# UTC timestamp. Nothing at or before it is stored again; see clear().
CLEARED_AT_META_KEY = "history_cleared_at"

# Furthest apart a legacy record's journald time and its task_history.json
# copy are matched as one run. The JSON history held only the last run, read
# when the Hardware page loaded, so its copy is dated by that poll: seconds to
# a few minutes after the run when someone was watching. Identical legacy runs
# further apart than this stay separate rows: matching any later row instead
# dropped a genuine earlier run when an identical one came later. A run polled
# later than this is stored twice, which loses nothing.
POLL_MATCH_WINDOW_SECONDS = 5 * 60

# Generation rates above this are not measurements: Lemonade emits a sentinel
# (1000000.0) when a completion is one token long and there is no elapsed
# generation time to divide by.
MAX_PLAUSIBLE_TPS = 10_000.0


def measurable_rate(rate: float, output_tokens: int) -> float:
    """Return the rate, or 0.0 when it cannot have been measured.

    The run itself is kept: its token counts and TTFT are real. Only the rate
    is dropped, and every aggregate skips non-positive rates.
    """
    try:
        value = float(rate)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value) or value <= 0.0:
        return 0.0
    if output_tokens < 2:
        # One token out means no generation interval to measure across.
        return 0.0
    if value > MAX_PLAUSIBLE_TPS:
        return 0.0
    return value

_TASK_COLUMNS = (
    "timestamp",
    "model",
    "input_tokens",
    "output_tokens",
    "prompt_tps",
    "gen_tps",
    "ttft_seconds",
    "total_seconds",
    "finish_reason",
    "finish_confidence",
)


@dataclass(frozen=True)
class TaskRow:
    """One completed inference as it is stored."""

    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    prompt_tps: float
    gen_tps: float
    ttft_seconds: float
    total_seconds: float
    finish_reason: str
    finish_confidence: str
    # False when the source log line had no timestamp; see insert_tasks().
    dated: bool = True
    # True when the time is journald's rather than the log line's own; see
    # insert_tasks().
    journal_dated: bool = False
    # True for rows from task_history.json, dated by when they were polled;
    # see insert_tasks().
    polled: bool = False


class MetricsStore:
    """Persistent task and hardware history."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._path = Path(db_path) if db_path is not None else Path(settings.metrics_db_path)
        self._lock = threading.Lock()
        self._ready = False

    @property
    def path(self) -> Path:
        return self._path

    # ── Connection handling ────────────────────────────────

    def _create_file(self) -> None:
        """Create the database file if it is missing, readable by its owner only.

        sqlite3.connect() would create it with the process umask, typically
        0644. SQLite gives the -wal and -shm files the main file's permissions,
        so creating the main file with 0600 covers them too. Files left by an
        earlier version with wider permissions are tightened by path.

        This runs once, from initialize(), before this store opens its first
        connection. An existing file is never opened here: closing any
        descriptor of an SQLite file drops every POSIX lock the process holds
        on it, including those of connections open in other threads
        (https://www.sqlite.org/howtocorrupt.html, section 2.2). A new file
        cannot carry locks yet, so creating it with O_EXCL is safe.
        """
        ensure_private_dir(self._path.parent)
        if not self._path.exists():
            try:
                descriptor = os.open(
                    self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE_MODE
                )
            except FileExistsError:
                # Created by someone else in the meantime: not ours to open.
                pass
            else:
                os.close(descriptor)
        for path in self._files():
            try:
                if stat.S_IMODE(path.stat().st_mode) & 0o077:
                    path.chmod(PRIVATE_FILE_MODE)
            except FileNotFoundError:
                continue

    def _files(self) -> tuple[Path, Path, Path]:
        """The database file and the WAL and shared-memory files beside it."""
        name = self._path.name
        return (
            self._path,
            self._path.with_name(name + "-wal"),
            self._path.with_name(name + "-shm"),
        )

    def _connect(self) -> sqlite3.Connection:
        # mode=rw: SQLite must not create the file itself. If it disappears
        # while LCC runs, the jobs fail and say so instead of SQLite quietly
        # recreating it with the umask's permissions. The next start creates it.
        connection = sqlite3.connect(
            f"{self._path.absolute().as_uri()}?mode=rw", uri=True, timeout=5.0
        )
        connection.row_factory = sqlite3.Row
        # Per connection, unlike journal_mode. In WAL mode NORMAL cannot corrupt
        # the database; a power cut may lose the last commits, which for
        # metrics sampled every few seconds is not worth an fsync each time.
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def initialize(self) -> None:
        """Create the schema once. Safe to call repeatedly."""
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            self._create_file()
            connection = self._connect()
            try:
                # WAL keeps the sampler's writes from blocking API reads.
                connection.execute("PRAGMA journal_mode=WAL")
                connection.executescript(_SCHEMA)
                connection.execute(
                    "INSERT OR IGNORE INTO metrics_meta (key, value) VALUES (?, ?)",
                    ("schema_version", str(SCHEMA_VERSION)),
                )
                connection.commit()
            finally:
                connection.close()
            self._ready = True

    def _write(self, statements):
        """Run a callable against a connection under the write lock."""
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                # One transaction for the reads and writes of the callable, so a
                # check such as the clear cut-off holds for the rows it lets in.
                connection.execute("BEGIN IMMEDIATE")
                result = statements(connection)
                connection.commit()
                return result
            except BaseException:
                with contextlib.suppress(sqlite3.Error):
                    connection.rollback()
                raise
            finally:
                connection.close()

    def _read(self, statements):
        self.initialize()
        connection = self._connect()
        try:
            return statements(connection)
        finally:
            connection.close()

    # ── Task records ───────────────────────────────────────

    def insert_tasks(self, rows: list[TaskRow]) -> int:
        """Store completed inferences, ignoring ones already recorded.

        Identity is (timestamp, model, input_tokens, output_tokens): two runs
        with identical numbers at different times are two rows, while the same
        record scraped twice stays one. Timestamps are stored as aware UTC
        ISO strings, so one instant always has one spelling: a naive one, as
        early versions wrote to task_history.json with utcnow(), is read as
        UTC. A row whose
        timestamp cannot be parsed is skipped rather than dated by guesswork.

        Rows completed at or before the last clear() are skipped: the journal
        still holds them, and they would otherwise come back on the next read.

        An undated row carries the time it was read, which changes on every
        scrape. Journal records are always dated (by Lemonade or by journald),
        so this only covers sources without any timestamp. Like the JSON
        history before it, such a row is matched on its metrics alone: it is
        skipped when a row with the same token counts, rate and duration
        exists. Once the history has been cleared it cannot be placed on
        either side of the cut-off, so it is skipped.

        A legacy record dated by journald may already be stored under a later
        time: the JSON history, and so its import, dated such records by when
        they were polled. It is skipped when a row with the same model, token
        counts and rate exists from its own time up to
        POLL_MATCH_WINDOW_SECONDS after it. Identical runs at different times
        are still told apart: a later run is never matched against an earlier
        row, nor an earlier run against a row more than the window later.

        The journal may also be read before the import (an import that failed
        on an earlier start, or a read endpoint that came first). So a polled
        row is skipped when a row with the same model, token counts and rate
        was stored before this call at or before its own time, within the same
        window, so either order pairs the same rows. Rows of the same call are
        not matched, so repeated runs in the JSON history stay separate rows.
        """
        if not rows:
            return 0

        accepted: list[TaskRow] = []
        payload = []
        for row in rows:
            moment = _utc(row.timestamp)
            if moment is None:
                continue
            accepted.append(row)
            payload.append((
                moment.isoformat(),
                moment.timestamp(),
                row.model,
                row.input_tokens,
                row.output_tokens,
                row.prompt_tps,
                measurable_rate(row.gen_tps, row.output_tokens),
                row.ttft_seconds,
                row.total_seconds,
                row.finish_reason,
                row.finish_confidence,
            ))

        def run(connection: sqlite3.Connection) -> int:
            before = connection.total_changes
            cleared_at = _cleared_at(connection)
            stored_before = connection.execute(
                "SELECT COALESCE(MAX(id), 0) FROM task_records"
            ).fetchone()[0]
            for row, values in zip(accepted, payload, strict=True):
                if cleared_at is not None and (not row.dated or values[1] <= cleared_at):
                    continue
                if not row.dated and _metrics_known(connection, row):
                    continue
                if row.journal_dated and _seen_since(connection, row, values[1]):
                    continue
                if row.polled and _seen_until(connection, row, values[1], stored_before):
                    continue
                connection.execute(
                    "INSERT OR IGNORE INTO task_records ("
                    "timestamp, ts_epoch, model, input_tokens, output_tokens, prompt_tps,"
                    " gen_tps, ttft_seconds, total_seconds, finish_reason, finish_confidence"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            return connection.total_changes - before

        return self._write(run)

    def get_tasks(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return the most recent tasks in a window, oldest first."""
        clauses, params = _range_clauses(since, until)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        def run(connection: sqlite3.Connection) -> list[dict]:
            cursor = connection.execute(
                f"SELECT {', '.join(_TASK_COLUMNS)} FROM task_records {where}"
                " ORDER BY ts_epoch DESC, id DESC LIMIT ?",
                (*params, max(1, limit)),
            )
            return [dict(row) for row in cursor.fetchall()]

        rows = self._read(run)
        rows.reverse()
        return rows

    def iter_tasks(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        batch_size: int = 1000,
    ) -> Iterator[list[dict]]:
        """Every task in a window, oldest first, in batches.

        Each batch is a short read of its own, so exporting years of history
        neither loads it all at once nor keeps a read open for the whole
        download. Batches continue after the last (ts_epoch, id) seen.
        """
        clauses, params = _range_clauses(since, until)
        after: tuple[float, int] | None = None
        while True:
            where = list(clauses)
            values: list[float | int] = list(params)
            if after is not None:
                where.append("(ts_epoch > ? OR (ts_epoch = ? AND id > ?))")
                values += [after[0], after[0], after[1]]
            query = (
                f"SELECT id, {', '.join(_TASK_COLUMNS)}, ts_epoch FROM task_records"
                + (f" WHERE {' AND '.join(where)}" if where else "")
                + " ORDER BY ts_epoch ASC, id ASC LIMIT ?"
            )
            arguments = (*values, max(1, batch_size))
            rows = self._read(
                lambda connection, query=query, arguments=arguments: connection.execute(
                    query, arguments
                ).fetchall()
            )
            if not rows:
                return
            after = (rows[-1]["ts_epoch"], rows[-1]["id"])
            yield [{column: row[column] for column in _TASK_COLUMNS} for row in rows]
            if len(rows) < batch_size:
                return

    def count_tasks(self) -> int:
        return self._read(
            lambda connection: connection.execute(
                "SELECT COUNT(*) FROM task_records"
            ).fetchone()[0]
        )

    def latest_task_timestamp(self) -> str | None:
        row = self._read(
            lambda connection: connection.execute(
                "SELECT timestamp FROM task_records ORDER BY ts_epoch DESC, id DESC LIMIT 1"
            ).fetchone()
        )
        return row[0] if row else None

    def _task_rows_in_window(self, start: datetime, end: datetime) -> list[dict]:
        def run(connection: sqlite3.Connection) -> list[sqlite3.Row]:
            return connection.execute(
                "SELECT ts_epoch, gen_tps, ttft_seconds, input_tokens, output_tokens"
                " FROM task_records WHERE ts_epoch >= ? AND ts_epoch <= ?"
                " ORDER BY ts_epoch ASC",
                (start.timestamp(), end.timestamp()),
            ).fetchall()

        return [dict(row) for row in self._read(run)]

    def task_series(
        self,
        start: datetime,
        end: datetime,
        bucket_seconds: int,
    ) -> list[dict]:
        """Time-bucketed task aggregates over a window."""
        return bucket_task_rows(self._task_rows_in_window(start, end), bucket_seconds)

    def output_token_percentile(
        self,
        start: datetime,
        end: datetime,
        fraction: float = 0.95,
    ) -> dict:
        """One percentile of output_tokens over a window.

        The scatter's size scale needs a single scalar, not every row: shipping
        30 days of runs to the client to compute one number was a full history
        transfer per page load. Only the column that feeds the percentile is
        read, and the aggregation reuses the same nearest-rank `percentile`
        the series summaries use, so the two never drift apart.

        Zero-token rows are excluded: a run that produced nothing carries no
        magnitude and would drag the percentile down.
        """

        def run(connection: sqlite3.Connection) -> list[int]:
            return [
                int(row[0])
                for row in connection.execute(
                    "SELECT output_tokens FROM task_records"
                    " WHERE ts_epoch >= ? AND ts_epoch <= ? AND output_tokens > 0",
                    (start.timestamp(), end.timestamp()),
                ).fetchall()
            ]

        values = self._read(run)
        return {
            "count": len(values),
            # None, not 0: an empty window has no ceiling, and a zero one would
            # make every mark render at maximum radius.
            "value": percentile([float(value) for value in values], fraction) if values else None,
        }

    def history_summary(self) -> dict:
        """Row counts and the oldest timestamp in each table.

        Backs the delete-history confirmation, which has to state what is about
        to be destroyed rather than guess at it.
        """

        def run(connection: sqlite3.Connection) -> dict:
            tasks = connection.execute("SELECT COUNT(*) FROM task_records").fetchone()[0]
            hardware = connection.execute(
                "SELECT COUNT(*) FROM hardware_samples"
            ).fetchone()[0]
            oldest_task = connection.execute(
                "SELECT timestamp FROM task_records ORDER BY ts_epoch ASC, id ASC LIMIT 1"
            ).fetchone()
            oldest_hardware = connection.execute(
                "SELECT timestamp FROM hardware_samples ORDER BY ts_epoch ASC, id ASC LIMIT 1"
            ).fetchone()
            return {
                "tasks": tasks,
                "hardware": hardware,
                "oldest_task": oldest_task[0] if oldest_task else None,
                "oldest_hardware": oldest_hardware[0] if oldest_hardware else None,
            }

        return self._read(run)

    def task_window(
        self,
        start: datetime,
        end: datetime,
        bucket_seconds: int,
    ) -> dict:
        """Buckets plus a summary over the whole window, from one read.

        The window percentiles come from the raw rows, not from the per-bucket
        percentiles: averaging percentiles would not be a percentile.
        """
        rows = self._task_rows_in_window(start, end)
        return {
            "buckets": bucket_task_rows(rows, bucket_seconds),
            "summary": summarize_task_rows(rows),
        }

    # ── Hardware samples ───────────────────────────────────

    def upsert_hardware_minute(self, aggregate: dict) -> None:
        """Write (or refresh) the aggregated row for one minute.

        A minute that began at or before the last clear() is not written: its
        running aggregate still holds samples taken before the clear.
        """

        def run(connection: sqlite3.Connection) -> None:
            cleared_at = _cleared_at(connection)
            if cleared_at is not None and _epoch(aggregate["timestamp"]) <= cleared_at:
                return
            connection.execute(
                "INSERT INTO hardware_samples ("
                "timestamp, ts_epoch, sample_count, ram_used_gb, ram_total_gb,"
                " ram_percent, ram_percent_min, ram_percent_max, cpu_percent,"
                " swap_used_gb, gpu_load_percent, gpu_temp_c, gpu_vram_used_gb,"
                " gpu_gtt_used_gb, temperatures"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(timestamp) DO UPDATE SET"
                " sample_count=excluded.sample_count,"
                " ram_used_gb=excluded.ram_used_gb,"
                " ram_total_gb=excluded.ram_total_gb,"
                " ram_percent=excluded.ram_percent,"
                " ram_percent_min=excluded.ram_percent_min,"
                " ram_percent_max=excluded.ram_percent_max,"
                " cpu_percent=excluded.cpu_percent,"
                " swap_used_gb=excluded.swap_used_gb,"
                " gpu_load_percent=excluded.gpu_load_percent,"
                " gpu_temp_c=excluded.gpu_temp_c,"
                " gpu_vram_used_gb=excluded.gpu_vram_used_gb,"
                " gpu_gtt_used_gb=excluded.gpu_gtt_used_gb,"
                " temperatures=excluded.temperatures",
                (
                    aggregate["timestamp"],
                    _epoch(aggregate["timestamp"]),
                    aggregate["sample_count"],
                    aggregate["ram_used_gb"],
                    aggregate["ram_total_gb"],
                    aggregate["ram_percent"],
                    aggregate["ram_percent_min"],
                    aggregate["ram_percent_max"],
                    aggregate["cpu_percent"],
                    aggregate["swap_used_gb"],
                    aggregate["gpu_load_percent"],
                    aggregate["gpu_temp_c"],
                    aggregate.get("gpu_vram_used_gb"),
                    aggregate.get("gpu_gtt_used_gb"),
                    json.dumps(aggregate.get("temperatures") or {}),
                ),
            )

        self._write(run)

    def get_hardware_minute(self, minute_start: datetime) -> dict | None:
        """The stored row for one minute, if there is one."""
        row = self._read(
            lambda connection: connection.execute(
                "SELECT * FROM hardware_samples WHERE ts_epoch = ?",
                (minute_start.timestamp(),),
            ).fetchone()
        )
        return dict(row) if row else None

    def count_hardware(self) -> int:
        return self._read(
            lambda connection: connection.execute(
                "SELECT COUNT(*) FROM hardware_samples"
            ).fetchone()[0]
        )

    def hardware_series(
        self,
        start: datetime,
        end: datetime,
        bucket_seconds: int,
    ) -> list[dict]:
        """Time-bucketed hardware aggregates over a window."""

        def run(connection: sqlite3.Connection) -> list[sqlite3.Row]:
            return connection.execute(
                "SELECT ts_epoch, sample_count, ram_used_gb, ram_total_gb, ram_percent,"
                " ram_percent_min, ram_percent_max, cpu_percent, swap_used_gb,"
                " gpu_load_percent, gpu_temp_c, gpu_vram_used_gb, gpu_gtt_used_gb,"
                " temperatures FROM hardware_samples WHERE ts_epoch >= ? AND ts_epoch <= ?"
                " ORDER BY ts_epoch ASC",
                (start.timestamp(), end.timestamp()),
            ).fetchall()

        return bucket_hardware_rows(
            [dict(row) for row in self._read(run)],
            bucket_seconds,
        )

    # ── Housekeeping ───────────────────────────────────────

    def prune(
        self,
        task_retention_days: int | None = None,
        hardware_retention_days: int | None = None,
        now: datetime | None = None,
    ) -> dict[str, int]:
        """Drop rows past their retention window. Returns rows removed.

        A retention of 0 (or less) means no limit for that table, never
        "delete everything".
        """
        moment = now or datetime.now(UTC)
        task_days = (
            task_retention_days
            if task_retention_days is not None
            else settings.task_retention_days
        )
        hardware_days = (
            hardware_retention_days
            if hardware_retention_days is not None
            else settings.hardware_retention_days
        )

        def delete_before(connection: sqlite3.Connection, table: str, days: int) -> int:
            if days <= 0:
                return 0
            cutoff = (moment - timedelta(days=days)).timestamp()
            removed = connection.execute(
                f"DELETE FROM {table} WHERE ts_epoch < ?", (cutoff,)
            ).rowcount
            return max(0, removed)

        def run(connection: sqlite3.Connection) -> dict[str, int]:
            return {
                "tasks": delete_before(connection, "task_records", task_days),
                "hardware": delete_before(connection, "hardware_samples", hardware_days),
            }

        return self._write(run)

    def clear(self, now: datetime | None = None) -> dict[str, int]:
        """Wipe both series, reporting the rows removed.

        The caller shows those counts back to the operator: an irreversible
        delete that answers "done" tells them nothing about what it took.

        The journal still holds the cleared tasks, so the time of the clear is
        stored with the delete, in the same transaction, and nothing completed
        at or before it is stored again.
        """
        moment = (now or datetime.now(UTC)).astimezone(UTC)

        def run(connection: sqlite3.Connection) -> dict[str, int]:
            tasks = connection.execute("DELETE FROM task_records").rowcount
            hardware = connection.execute("DELETE FROM hardware_samples").rowcount
            previous = _cleared_at(connection)
            if previous is None or moment.timestamp() > previous:
                _set_meta(connection, CLEARED_AT_META_KEY, moment.isoformat())
            return {"tasks": max(0, tasks), "hardware": max(0, hardware)}

        return self._write(run)

    def get_meta(self, key: str) -> str | None:
        row = self._read(
            lambda connection: connection.execute(
                "SELECT value FROM metrics_meta WHERE key = ?", (key,)
            ).fetchone()
        )
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._write(lambda connection: _set_meta(connection, key, value))


# ── Bucketing and aggregation ──────────────────────────────


def resolve_range(name: str | None) -> tuple[str, timedelta, int]:
    """Map a range selector onto its window and bucket width.

    No selector means the default range. An unknown one raises ValueError
    rather than quietly answering for another window: a CSV export for a
    range that does not exist would otherwise hold a different day's data.
    """
    key = (name or DEFAULT_RANGE).strip().lower()
    if key not in RANGE_WINDOWS:
        raise ValueError(f"range must be one of: {', '.join(RANGE_WINDOWS)}")
    window, bucket_seconds = RANGE_WINDOWS[key]
    return key, window, bucket_seconds


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile over an unsorted list.

    Nearest-rank always returns an observed value, which is what makes p95
    meaningful on the small per-bucket samples this store produces.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = math.ceil(fraction * len(ordered))
    index = min(max(rank - 1, 0), len(ordered) - 1)
    return round(ordered[index], 2)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def bucket_start(epoch: float, bucket_seconds: int) -> float:
    """Floor an epoch to its bucket boundary."""
    return math.floor(epoch / bucket_seconds) * bucket_seconds


def bucket_task_rows(rows: list[dict], bucket_seconds: int) -> list[dict]:
    """Group task rows into fixed buckets and aggregate each one.

    Empty buckets are omitted rather than zero-filled, so a quiet range simply
    yields fewer points instead of a flat line at zero.
    """
    if bucket_seconds <= 0:
        bucket_seconds = 60

    grouped: dict[float, list[dict]] = {}
    for row in rows:
        grouped.setdefault(bucket_start(row["ts_epoch"], bucket_seconds), []).append(row)

    buckets: list[dict] = []
    for start in sorted(grouped):
        members = grouped[start]
        gen_tps = _measured_rates(members)
        ttft = [float(item["ttft_seconds"]) for item in members]
        input_tokens = sum(int(item["input_tokens"]) for item in members)
        output_tokens = sum(int(item["output_tokens"]) for item in members)
        buckets.append(
            {
                "t": _iso(start),
                "count": len(members),
                "gen_tps_mean": _mean(gen_tps),
                "gen_tps_p50": percentile(gen_tps, 0.5),
                "gen_tps_p95": percentile(gen_tps, 0.95),
                "ttft_mean": _mean(ttft),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }
        )
    return buckets


def summarize_task_rows(rows: list[dict]) -> dict:
    """Aggregate an entire window into one summary row."""
    gen_tps = _measured_rates(rows)
    ttft = [float(row["ttft_seconds"]) for row in rows]
    input_tokens = sum(int(row["input_tokens"]) for row in rows)
    output_tokens = sum(int(row["output_tokens"]) for row in rows)
    return {
        "count": len(rows),
        "gen_tps_mean": _mean(gen_tps),
        "gen_tps_p50": percentile(gen_tps, 0.5),
        "gen_tps_p95": percentile(gen_tps, 0.95),
        "ttft_mean": _mean(ttft),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def bucket_hardware_rows(rows: list[dict], bucket_seconds: int) -> list[dict]:
    """Group per-minute hardware rows into fixed buckets and aggregate."""
    if bucket_seconds <= 0:
        bucket_seconds = 60

    grouped: dict[float, list[dict]] = {}
    for row in rows:
        grouped.setdefault(bucket_start(row["ts_epoch"], bucket_seconds), []).append(row)

    buckets: list[dict] = []
    for start in sorted(grouped):
        members = grouped[start]
        ram_percent_mins = _numbers(members, "ram_percent_min")
        ram_percent_maxes = _numbers(members, "ram_percent_max")
        buckets.append(
            {
                "t": _iso(start),
                "count": sum(int(item.get("sample_count") or 0) for item in members),
                "ram_used_gb": _mean(_numbers(members, "ram_used_gb")),
                "ram_total_gb": _mean(_numbers(members, "ram_total_gb")),
                "ram_percent": _mean(_numbers(members, "ram_percent")),
                "ram_percent_min": round(min(ram_percent_mins), 2) if ram_percent_mins else 0.0,
                "ram_percent_max": round(max(ram_percent_maxes), 2) if ram_percent_maxes else 0.0,
                "cpu_percent": _mean(_numbers(members, "cpu_percent")),
                "swap_used_gb": _mean(_numbers(members, "swap_used_gb")),
                "gpu_load_percent": _optional_mean(members, "gpu_load_percent"),
                "gpu_temp_c": _optional_mean(members, "gpu_temp_c"),
                "gpu_vram_used_gb": _optional_mean(members, "gpu_vram_used_gb"),
                "gpu_gtt_used_gb": _optional_mean(members, "gpu_gtt_used_gb"),
                "temps": _merge_temperatures(members),
            }
        )
    return buckets


def _measured_rates(rows: list[dict]) -> list[float]:
    """Generation rates that were measured; zeroed sentinels are skipped."""
    return [rate for row in rows if (rate := float(row["gen_tps"])) > 0.0]


def _numbers(rows: list[dict], key: str) -> list[float]:
    return [float(row[key]) for row in rows if row.get(key) is not None]


def _optional_mean(rows: list[dict], key: str) -> float | None:
    """Mean of a metric that may be absent on this host (no GPU, no sensors)."""
    values = _numbers(rows, key)
    return _mean(values) if values else None


def _merge_temperatures(rows: list[dict]) -> dict[str, float]:
    """Mean per sensor label across the bucket."""
    totals: dict[str, list[float]] = {}
    for row in rows:
        raw = row.get("temperatures")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                raw = {}
        if not isinstance(raw, dict):
            continue
        for label, value in raw.items():
            try:
                totals.setdefault(label, []).append(float(value))
            except (TypeError, ValueError):
                continue
    return {label: _mean(values) for label, values in totals.items()}


# ── Helpers ────────────────────────────────────────────────


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def _utc(timestamp: str) -> datetime | None:
    """Parse an ISO timestamp as aware UTC; a naive one is taken as UTC."""
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _epoch(timestamp: str) -> float:
    """Epoch seconds for one of this package's own ISO timestamps."""
    moment = _utc(timestamp)
    if moment is None:
        raise ValueError(f"not an ISO-8601 timestamp: {timestamp!r}")
    return moment.timestamp()


def _set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO metrics_meta (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def _cleared_at(connection: sqlite3.Connection) -> float | None:
    """Epoch of the last clear(), or None if the history was never cleared."""
    row = connection.execute(
        "SELECT value FROM metrics_meta WHERE key = ?", (CLEARED_AT_META_KEY,)
    ).fetchone()
    if row is None:
        return None
    try:
        return datetime.fromisoformat(row[0]).timestamp()
    except (TypeError, ValueError):
        return None


def _metrics_known(connection: sqlite3.Connection, row: TaskRow) -> bool:
    """Whether a row with these token counts, rate and duration is stored."""
    return (
        connection.execute(
            "SELECT 1 FROM task_records WHERE input_tokens = ? AND output_tokens = ?"
            " AND gen_tps = ? AND total_seconds = ? LIMIT 1",
            (
                row.input_tokens,
                row.output_tokens,
                measurable_rate(row.gen_tps, row.output_tokens),
                row.total_seconds,
            ),
        ).fetchone()
        is not None
    )


def _seen_since(connection: sqlite3.Connection, row: TaskRow, epoch: float) -> bool:
    """Whether the same run is stored at `epoch` or up to the poll window after it."""
    return (
        connection.execute(
            "SELECT 1 FROM task_records WHERE input_tokens = ? AND output_tokens = ?"
            " AND model = ? AND gen_tps = ? AND ts_epoch BETWEEN ? AND ? LIMIT 1",
            (
                row.input_tokens,
                row.output_tokens,
                row.model,
                measurable_rate(row.gen_tps, row.output_tokens),
                epoch,
                epoch + POLL_MATCH_WINDOW_SECONDS,
            ),
        ).fetchone()
        is not None
    )


def _seen_until(
    connection: sqlite3.Connection, row: TaskRow, epoch: float, last_id: int
) -> bool:
    """Whether the same run is among rows up to `last_id`, at `epoch` or up to
    the poll window before it."""
    return (
        connection.execute(
            "SELECT 1 FROM task_records WHERE input_tokens = ? AND output_tokens = ?"
            " AND model = ? AND gen_tps = ? AND ts_epoch BETWEEN ? AND ? AND id <= ?"
            " LIMIT 1",
            (
                row.input_tokens,
                row.output_tokens,
                row.model,
                measurable_rate(row.gen_tps, row.output_tokens),
                epoch - POLL_MATCH_WINDOW_SECONDS,
                epoch,
                last_id,
            ),
        ).fetchone()
        is not None
    )


def _range_clauses(
    since: datetime | None,
    until: datetime | None,
) -> tuple[list[str], list[float]]:
    clauses: list[str] = []
    params: list[float] = []
    if since is not None:
        clauses.append("ts_epoch >= ?")
        params.append(since.timestamp())
    if until is not None:
        clauses.append("ts_epoch <= ?")
        params.append(until.timestamp())
    return clauses, params


_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ts_epoch REAL NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    prompt_tps REAL NOT NULL DEFAULT 0,
    gen_tps REAL NOT NULL DEFAULT 0,
    ttft_seconds REAL NOT NULL DEFAULT 0,
    total_seconds REAL NOT NULL DEFAULT 0,
    finish_reason TEXT NOT NULL DEFAULT 'unknown',
    finish_confidence TEXT NOT NULL DEFAULT 'unknown',
    UNIQUE (timestamp, model, input_tokens, output_tokens)
);

CREATE INDEX IF NOT EXISTS idx_task_records_ts ON task_records (ts_epoch);
CREATE INDEX IF NOT EXISTS idx_task_records_tokens
    ON task_records (input_tokens, output_tokens);

CREATE TABLE IF NOT EXISTS hardware_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL UNIQUE,
    ts_epoch REAL NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    ram_used_gb REAL,
    ram_total_gb REAL,
    ram_percent REAL,
    ram_percent_min REAL,
    ram_percent_max REAL,
    cpu_percent REAL,
    swap_used_gb REAL,
    gpu_load_percent REAL,
    gpu_temp_c REAL,
    -- amdgpu memory in use; NULL where the host does not report it. On APUs
    -- most of a model lives in GTT rather than dedicated VRAM.
    gpu_vram_used_gb REAL,
    gpu_gtt_used_gb REAL,
    temperatures TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_hardware_samples_ts ON hardware_samples (ts_epoch);

CREATE TABLE IF NOT EXISTS metrics_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
