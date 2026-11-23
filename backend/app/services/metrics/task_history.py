"""Task performance history, persisted in SQLite for long-run trends.

Every completed inference the journal still holds is recorded, not just the
most recent one, so nothing is lost between two polls or while no UI is open.
The legacy JSON file is imported once on first start and then left alone.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.capabilities import capabilities
from app.models.schemas import LastTaskStats
from app.services.log_parser import (
    TaskTelemetryRecord,
    infer_finish_reason,
    parse_task_records,
)
from app.services.metrics.store import MetricsStore, TaskRow

HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "task_history.json"
MIGRATION_META_KEY = "task_history_json_imported"

# How much journal to scan per sampler tick. The window has to comfortably
# outrun the 15s sampling interval so a burst of inferences is never missed.
JOURNAL_SCAN_LINES = 500


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

    @property
    def store(self) -> MetricsStore:
        return self._store

    def use_store(self, store: MetricsStore) -> None:
        """Point the history at a different database (tests, relocation)."""
        self._store = store

    # ── Ingestion ──────────────────────────────────────────

    def refresh_from_logs(self) -> int:
        """Scrape the journal and store every task it still carries.

        Returns the number of newly stored records. Records already known are
        dropped by the store's (timestamp, model, in, out) identity, so calling
        this on every poll and on every sampler tick is cheap and idempotent.
        """
        if not capabilities.cmd_journalctl:
            return 0
        try:
            records = parse_task_records(n_lines=JOURNAL_SCAN_LINES)
        except Exception:
            # A journal that cannot be read must never break the caller: the
            # sampler keeps ticking and the endpoints keep serving what exists.
            return 0
        return self.ingest(records)

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
            self.refresh_from_logs()
        return self._store.get_tasks(since=since, until=until, limit=n)

    def series(self, start: datetime, end: datetime, bucket_seconds: int) -> list[dict]:
        return self._store.task_series(start, end, bucket_seconds)

    def window(self, start: datetime, end: datetime, bucket_seconds: int) -> dict:
        """Buckets plus a whole-window summary."""
        return self._store.task_window(start, end, bucket_seconds)

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
        limit: int = 100_000,
        refresh: bool = True,
    ) -> str:
        if refresh:
            self.refresh_from_logs()
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(TaskRecord.__annotations__.keys()))
        writer.writeheader()
        for row in self._store.get_tasks(since=since, until=until, limit=limit):
            writer.writerow(row)
        return output.getvalue()

    # ── One-off migration ──────────────────────────────────

    def migrate_legacy_json(self, path: Path | None = None) -> int:
        """Import the old rolling JSON history once, then never again.

        The file itself is left in place: it is the previous version's data and
        removing it would make a downgrade lossy.
        """
        if self._store.get_meta(MIGRATION_META_KEY):
            return 0
        source = path or HISTORY_FILE
        imported = 0
        if source.exists():
            try:
                data = json.loads(source.read_text(encoding="utf-8"))
                rows = [
                    _row_from_legacy(item)
                    for item in data.get("tasks", [])
                    if isinstance(item, dict)
                ]
                imported = self._store.insert_tasks([row for row in rows if row])
            except (OSError, TypeError, ValueError):
                imported = 0
        self._store.set_meta(MIGRATION_META_KEY, datetime.now(UTC).isoformat())
        return imported


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
        )
    except (KeyError, TypeError, ValueError):
        return None


# Shared instance: the background sampler and the API read the same history.
task_history = TaskHistory()
