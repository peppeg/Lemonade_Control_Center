"""Task performance history, persisted in SQLite for long-run trends.

Every completed inference the journal still holds is recorded, not just the
most recent one, so nothing is lost between two polls or while no UI is open.
The legacy JSON file is imported once on first start and then left alone.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.capabilities import capabilities
from app.models.schemas import LastTaskStats
from app.services.log_parser import (
    JournalReadError,
    TaskJournalRead,
    TaskTelemetryRecord,
    infer_finish_reason,
    read_task_journal,
)
from app.services.metrics.store import MetricsStore, TaskRow

log = logging.getLogger(__name__)

HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "task_history.json"
MIGRATION_META_KEY = "task_history_json_imported"

# Where the journal was last read up to, kept in metrics_meta so a restart
# resumes there: journald's cursor of the last entry read, and when journald
# received that entry.
JOURNAL_CURSOR_META_KEY = "journal_cursor"
JOURNAL_CURSOR_TIME_META_KEY = "journal_cursor_time"

# Each read takes up to JOURNAL_MAX_LINES entries after the saved cursor, so a
# backlog (LCC was stopped, or reads failed for a while) is read in full over
# a few reads. A fixed window of recent lines could lose a run: a model load
# can log hundreds of lines between two ticks. Without a cursor, the very
# first read takes the most recent JOURNAL_SCAN_LINES. When the cursor cannot
# be used, reads go by time from the saved receive time, JOURNAL_OVERLAP
# earlier to be safe.
JOURNAL_SCAN_LINES = 500
JOURNAL_MAX_LINES = 20_000
JOURNAL_OVERLAP = timedelta(minutes=2)


@dataclass
class TaskRecord:
    """The record shape /api/metrics/tasks has always returned."""

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


class TaskHistory:
    def __init__(self, store: MetricsStore | None = None) -> None:
        self._store = store or MetricsStore()
        # One journal read at a time: the sampler and a read endpoint would
        # otherwise read the same entries and race to save the cursor.
        self._read_lock = threading.Lock()

    @property
    def store(self) -> MetricsStore:
        return self._store

    def use_store(self, store: MetricsStore) -> None:
        """Point the history at a different database (tests, relocation)."""
        with self._read_lock:
            self._store = store

    # ── Ingestion ──────────────────────────────────────────

    def refresh_from_logs(self) -> int:
        """Scrape the journal and store every task it still carries.

        Returns the number of newly stored records. Records already known are
        dropped by the store's (timestamp, model, in, out) identity, so calling
        this on every poll and on every sampler tick is cheap and idempotent.

        Each read continues after the journal cursor the previous successful
        read saved in metrics_meta, so nothing journald received in between is
        skipped: not while LCC was stopped, not during a stretch of failed
        reads, and not when more lines arrived than one read takes. The cursor
        is saved only once the records are stored.

        Raises when the journal cannot be read or the store cannot be written;
        the task sampler logs it, and the next read starts from the same
        cursor. Read endpoints use _refresh_quietly().
        """
        if not capabilities.cmd_journalctl:
            return 0
        with self._read_lock:
            cursor = self._store.get_meta(JOURNAL_CURSOR_META_KEY)
            read = self._read_journal(cursor)
            stored = self.ingest(read.records)
            if read.cursor and read.cursor != cursor:
                self._store.set_meta(JOURNAL_CURSOR_META_KEY, read.cursor)
                if read.cursor_time:
                    self._store.set_meta(JOURNAL_CURSOR_TIME_META_KEY, read.cursor_time)
        return stored

    def _read_journal(self, cursor: str | None) -> TaskJournalRead:
        """Read on from the saved cursor, or by time when it cannot be used."""
        if cursor:
            try:
                read = read_task_journal(n_lines=JOURNAL_MAX_LINES, after_cursor=cursor)
            except JournalReadError as error:
                # A cursor journalctl cannot seek to (malformed, or from a
                # journal since replaced) fails the read. Reading by time
                # replaces it; when the journal itself cannot be read, that
                # fails too and the cursor is kept.
                log.info(
                    "Cannot read the journal after the saved cursor (%s); reading by time",
                    error,
                )
            else:
                if read.entries >= JOURNAL_MAX_LINES:
                    log.warning(
                        "More than %d journal lines arrived since the last read;"
                        " the rest is read on the next ones",
                        JOURNAL_MAX_LINES,
                    )
                return read

        since = _parse_time(self._store.get_meta(JOURNAL_CURSOR_TIME_META_KEY))
        if since is None:
            return read_task_journal(n_lines=JOURNAL_SCAN_LINES)
        read = read_task_journal(n_lines=JOURNAL_MAX_LINES, since=since - JOURNAL_OVERLAP)
        if read.entries >= JOURNAL_MAX_LINES:
            log.warning(
                "More than %d journal lines arrived since %s; runs logged among the"
                " oldest of them may be missing from the history",
                JOURNAL_MAX_LINES,
                since.isoformat(),
            )
        return read

    def _refresh_quietly(self) -> None:
        """Refresh before a read, serving what is stored if that fails.

        The task sampler runs the same refresh every few seconds and logs its
        failures, so a read does not report them a second time.
        """
        try:
            self.refresh_from_logs()
        except Exception as error:
            log.debug("Task history refresh before a read failed: %s", error)

    def ingest(self, records: list[TaskTelemetryRecord]) -> int:
        """Store already-parsed telemetry records."""
        rows = [_to_row(record) for record in records if record.output_tokens]
        return self._store.insert_tasks(rows)

    # ── Reads ──────────────────────────────────────────────

    def get_recent(
        self,
        n: int = 20,
        since: datetime | None = None,
        until: datetime | None = None,
        refresh: bool = True,
    ) -> list[dict]:
        if refresh:
            self._refresh_quietly()
        return self._store.get_tasks(since=since, until=until, limit=n)

    def count(self) -> int:
        return self._store.count_tasks()

    def clear(self, now: datetime | None = None) -> dict[str, int]:
        """Wipe the persisted history, returning the rows removed per table.

        Tasks the journal still holds are not stored again; see MetricsStore.clear().
        """
        return self._store.clear(now)

    def export_csv(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        refresh: bool = True,
    ) -> Iterator[str]:
        """Every task in the window as CSV, oldest first, a chunk at a time.

        Nothing is left out: task records are kept indefinitely, and an export
        capped at a row count would silently drop the oldest ones.
        """
        if refresh:
            self._refresh_quietly()
        fieldnames = list(TaskRecord.__annotations__.keys())
        yield _csv_chunk(fieldnames, [], header=True)
        for batch in self._store.iter_tasks(since=since, until=until):
            yield _csv_chunk(fieldnames, batch)

    # ── One-off migration ──────────────────────────────────

    def migrate_legacy_json(self, path: Path | None = None) -> int:
        """Import the old rolling JSON history once, then never again.

        The file itself is left in place: it is the previous version's data and
        removing it would make a downgrade lossy.

        The import is marked done only once it succeeded, or when there is no
        file to import. A file that cannot be read or parsed raises
        LegacyHistoryError and is tried again on the next start; the collector
        logs it once per start, so a file that stays corrupt is not retried in
        a loop. Single unusable entries in a readable file are skipped.
        """
        if self._store.get_meta(MIGRATION_META_KEY):
            return 0
        source = path or HISTORY_FILE
        imported = 0
        if source.exists():
            rows = _read_legacy_rows(source)
            imported = self._store.insert_tasks(rows)
        self._store.set_meta(MIGRATION_META_KEY, datetime.now(UTC).isoformat())
        return imported


class LegacyHistoryError(Exception):
    """task_history.json exists but cannot be imported."""


def _read_legacy_rows(source: Path) -> list[TaskRow]:
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        # ValueError covers both invalid JSON and invalid UTF-8.
        raise LegacyHistoryError(f"cannot read {source}: {error}") from error
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list):
        raise LegacyHistoryError(f"{source} holds no list of tasks")
    rows = [_row_from_legacy(item) for item in tasks if isinstance(item, dict)]
    return [row for row in rows if row]


def _parse_time(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def _csv_chunk(fieldnames: list[str], rows: list[dict], *, header: bool = False) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    if header:
        writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _to_row(record: TaskTelemetryRecord) -> TaskRow:
    # Reuse the parser's finish-reason inference so a stored row carries the
    # same verdict the live /logs/last-task view shows for the same numbers.
    finish = infer_finish_reason(
        LastTaskStats(
            available=True,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
        ),
        None,
    )
    return TaskRow(
        timestamp=record.timestamp,
        model=record.model,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        prompt_tps=record.prompt_eval_tps,
        gen_tps=record.generation_tps,
        ttft_seconds=record.ttft_seconds,
        total_seconds=record.total_duration_seconds,
        finish_reason=finish.reason,
        # .value, not str(): the enum's str() spells "FinishReasonConfidence.
        # INFERRED", which every other endpoint reports as plain "inferred".
        finish_confidence=finish.confidence.value,
        dated=record.dated,
        journal_dated=record.journal_dated,
    )


def _row_from_legacy(item: dict) -> TaskRow | None:
    """Map a legacy JSON entry onto a stored row, skipping unusable ones."""
    try:
        return TaskRow(
            timestamp=str(item["timestamp"]),
            model=str(item.get("model") or "unknown"),
            input_tokens=int(item.get("input_tokens") or 0),
            output_tokens=int(item.get("output_tokens") or 0),
            prompt_tps=float(item.get("prompt_tps") or 0),
            gen_tps=float(item.get("gen_tps") or 0),
            ttft_seconds=float(item.get("ttft_seconds") or 0),
            total_seconds=float(item.get("total_seconds") or 0),
            finish_reason=str(item.get("finish_reason") or "unknown"),
            finish_confidence=str(item.get("finish_confidence") or "unknown"),
            polled=True,
        )
    except (KeyError, TypeError, ValueError):
        return None


# Shared instance: the background sampler and the API read the same history.
task_history = TaskHistory()
