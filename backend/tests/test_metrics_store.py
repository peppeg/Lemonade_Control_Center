import json
import os
import sqlite3
import stat
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.log_parser import JournalReadError, extract_task_records
from app.services.metrics.store import (
    CLEARED_AT_META_KEY,
    MetricsStore,
    TaskRow,
    bucket_hardware_rows,
    bucket_start,
    bucket_task_rows,
    measurable_rate,
    percentile,
    resolve_range,
)
from app.services.metrics.task_history import (
    MIGRATION_META_KEY,
    LegacyHistoryError,
    TaskHistory,
)

FIXTURE = Path(__file__).parent / "fixtures" / "lemond_journal_11_7.log"
BASE = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path) -> MetricsStore:
    return MetricsStore(tmp_path / "lcc_metrics.db")


def make_row(
    offset_seconds: float = 0,
    gen_tps: float = 15.0,
    model: str = "Gemma-4-12B-it-MTP-GGUF",
    input_tokens: int = 91,
    output_tokens: int = 61,
    ttft: float = 1.0,
) -> TaskRow:
    return TaskRow(
        timestamp=(BASE + timedelta(seconds=offset_seconds)).isoformat(),
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        prompt_tps=round(input_tokens / ttft, 2),
        gen_tps=gen_tps,
        ttft_seconds=ttft,
        total_seconds=round(ttft + output_tokens / gen_tps, 1),
        finish_reason="stop",
        finish_confidence="inferred",
    )


# ── Schema and basic storage ───────────────────────────────


def test_store_creates_its_database_in_wal_mode(store):
    store.initialize()

    assert store.path.exists()
    connection = store._connect()
    try:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert mode.lower() == "wal"
    assert "idx_task_records_ts" in indexes
    assert "idx_hardware_samples_ts" in indexes


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_database_files_are_owner_only(tmp_path):
    previous = os.umask(0o022)
    try:
        store = MetricsStore(tmp_path / "data" / "lcc_metrics.db")
        store.insert_tasks([make_row(0)])
        # Hold a connection open so the WAL and shared-memory files exist.
        connection = sqlite3.connect(store.path)
        connection.execute("SELECT COUNT(*) FROM task_records").fetchone()
        paths = [store.path, *(store.path.with_name(store.path.name + s) for s in ("-wal", "-shm"))]
        modes = {path.name: stat.S_IMODE(path.stat().st_mode) for path in paths}
        connection.close()
    finally:
        os.umask(previous)

    assert modes == {path.name: 0o600 for path in paths}
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_an_existing_world_readable_database_is_tightened(tmp_path):
    path = tmp_path / "lcc_metrics.db"
    sqlite3.connect(path).close()
    path.chmod(0o644)

    MetricsStore(path).initialize()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_wal_and_shm_files_left_by_an_earlier_run_are_tightened(tmp_path, monkeypatch):
    path = tmp_path / "lcc_metrics.db"
    sqlite3.connect(path).close()
    leftovers = [path.with_name(path.name + suffix) for suffix in ("-wal", "-shm")]
    for leftover in leftovers:
        leftover.touch()
        leftover.chmod(0o644)
    # SQLite removes both files when its last connection closes, so record the
    # modes they are given instead of reading them back afterwards.
    modes: dict[Path, int] = {}
    real_chmod = os.chmod

    def spy_chmod(target, mode, *args, **kwargs):
        modes[Path(target)] = mode
        return real_chmod(target, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", spy_chmod)

    MetricsStore(path).initialize()

    assert [modes.get(leftover) for leftover in leftovers] == [0o600, 0o600]


@pytest.fixture
def opened_paths(monkeypatch):
    """Every path Python itself opens, as opposed to SQLite's own opens."""
    opened: list[Path] = []
    real_os_open = os.open
    real_open = open

    def spy_os_open(path, *args, **kwargs):
        opened.append(Path(path))
        return real_os_open(path, *args, **kwargs)

    def spy_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)):
            opened.append(Path(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy_os_open)
    monkeypatch.setattr("builtins.open", spy_open)
    return opened


def _exercise(store: MetricsStore) -> None:
    store.insert_tasks([make_row(0), make_row(60)])
    store.get_tasks()
    store.upsert_hardware_minute(
        {
            "timestamp": BASE.isoformat(),
            "sample_count": 1,
            "ram_used_gb": 1.0,
            "ram_total_gb": 2.0,
            "ram_percent": 50.0,
            "ram_percent_min": 50.0,
            "ram_percent_max": 50.0,
            "cpu_percent": 1.0,
            "swap_used_gb": 0.0,
            "gpu_load_percent": None,
            "gpu_temp_c": None,
        }
    )
    store.history_summary()
    store.set_meta("key", "value")
    store.get_meta("key")
    store.prune(task_retention_days=1, hardware_retention_days=1, now=BASE)
    store.clear()


def test_connections_never_open_the_database_file_outside_sqlite(store, opened_paths):
    """Closing any descriptor of the file would drop SQLite's POSIX locks.

    SQLite holds those locks per process, so a close() in one thread releases
    the locks of connections open in other threads.
    """
    store.initialize()
    opened_paths.clear()

    _exercise(store)

    assert not set(opened_paths) & set(store._files())


def test_an_existing_database_is_not_opened_outside_sqlite_on_start(tmp_path, opened_paths):
    path = tmp_path / "lcc_metrics.db"
    MetricsStore(path).insert_tasks([make_row(0)])
    opened_paths.clear()

    restarted = MetricsStore(path)
    restarted.initialize()

    assert path not in opened_paths
    assert restarted.count_tasks() == 1


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_a_database_removed_while_running_is_not_recreated_with_the_umask(tmp_path):
    previous = os.umask(0o022)
    try:
        store = MetricsStore(tmp_path / "lcc_metrics.db")
        store.insert_tasks([make_row(0)])
        for path in store._files():
            path.unlink(missing_ok=True)

        with pytest.raises(sqlite3.OperationalError):
            store.insert_tasks([make_row(60)])
    finally:
        os.umask(previous)

    assert not store.path.exists()
    # The next start creates it again, owner-only.
    MetricsStore(store.path).initialize()
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600


def test_hardware_samples_have_nullable_gpu_memory_columns(store):
    store.initialize()
    connection = sqlite3.connect(store.path)
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(hardware_samples)")}
    connection.close()

    for name in ("gpu_vram_used_gb", "gpu_gtt_used_gb"):
        assert columns[name][2] == "REAL"
        assert columns[name][3] == 0  # Nullable.


def test_empty_store_returns_empty_series_not_errors(store):
    end = datetime.now(UTC)
    start = end - timedelta(days=30)

    assert store.get_tasks() == []
    assert store.task_series(start, end, 3600) == []
    assert store.hardware_series(start, end, 3600) == []
    assert store.count_tasks() == 0
    assert store.count_hardware() == 0
    assert store.latest_task_timestamp() is None


# ── Deduplication ──────────────────────────────────────────


def test_identical_numbers_at_different_timestamps_are_two_rows(store):
    """Two separate runs that happen to perform the same are two data points."""
    stored = store.insert_tasks([make_row(0), make_row(60)])

    assert stored == 2
    assert store.count_tasks() == 2


def test_the_same_record_seen_twice_is_stored_once(store):
    """The sampler rescans an overlapping journal window on every tick."""
    store.insert_tasks([make_row(0)])
    stored_again = store.insert_tasks([make_row(0)])

    assert stored_again == 0
    assert store.count_tasks() == 1


def test_dedup_distinguishes_model_and_token_counts(store):
    store.insert_tasks([make_row(0)])
    store.insert_tasks([make_row(0, model="Other-Model")])
    store.insert_tasks([make_row(0, output_tokens=62)])

    assert store.count_tasks() == 3


def test_rescanning_the_whole_fixture_journal_is_idempotent(store):
    history = TaskHistory(store)
    records = extract_task_records(FIXTURE.read_text(encoding="utf-8").splitlines())

    assert history.ingest(records) == 9
    assert history.ingest(records) == 0
    assert store.count_tasks() == 9


# ── Windowed reads ─────────────────────────────────────────


def test_get_tasks_filters_by_window_and_returns_oldest_first(store):
    store.insert_tasks([make_row(offset) for offset in (0, 60, 120, 180)])

    rows = store.get_tasks(
        since=BASE + timedelta(seconds=60),
        until=BASE + timedelta(seconds=120),
    )

    assert [row["timestamp"] for row in rows] == [
        (BASE + timedelta(seconds=60)).isoformat(),
        (BASE + timedelta(seconds=120)).isoformat(),
    ]


def test_get_tasks_limit_keeps_the_newest_records(store):
    store.insert_tasks([make_row(offset) for offset in (0, 60, 120, 180)])

    rows = store.get_tasks(limit=2)

    assert [row["timestamp"] for row in rows] == [
        (BASE + timedelta(seconds=120)).isoformat(),
        (BASE + timedelta(seconds=180)).isoformat(),
    ]


def test_get_tasks_on_an_empty_window_is_an_empty_list(store):
    store.insert_tasks([make_row(0)])

    assert store.get_tasks(since=BASE + timedelta(days=1)) == []


# ── Bucketing and aggregation arithmetic ───────────────────


def test_percentile_uses_nearest_rank():
    values = [float(n) for n in range(1, 101)]

    assert percentile(values, 0.5) == 50.0
    assert percentile(values, 0.95) == 95.0
    assert percentile([7.0], 0.95) == 7.0
    assert percentile([], 0.5) == 0.0


def test_percentile_ignores_input_order():
    assert percentile([9.0, 1.0, 5.0, 3.0, 7.0], 0.5) == 5.0
    assert percentile([9.0, 1.0, 5.0, 3.0, 7.0], 0.95) == 9.0


def test_bucket_start_floors_to_the_bucket_boundary():
    assert bucket_start(3661, 60) == 3660
    assert bucket_start(3661, 900) == 3600
    assert bucket_start(3600, 3600) == 3600


def test_bucket_task_rows_aggregates_each_bucket():
    minute = BASE.timestamp()
    rows = [
        {"ts_epoch": minute + 1, "gen_tps": 10.0, "ttft_seconds": 1.0,
         "input_tokens": 10, "output_tokens": 100},
        {"ts_epoch": minute + 30, "gen_tps": 20.0, "ttft_seconds": 3.0,
         "input_tokens": 20, "output_tokens": 200},
        # Second bucket, one minute later.
        {"ts_epoch": minute + 61, "gen_tps": 30.0, "ttft_seconds": 5.0,
         "input_tokens": 30, "output_tokens": 300},
    ]

    buckets = bucket_task_rows(rows, 60)

    assert len(buckets) == 2
    first, second = buckets
    assert first["t"] == BASE.isoformat()
    assert first["count"] == 2
    assert first["gen_tps_mean"] == 15.0
    assert first["gen_tps_p50"] == 10.0      # nearest rank of two samples
    assert first["gen_tps_p95"] == 20.0
    assert first["ttft_mean"] == 2.0
    assert first["input_tokens"] == 30
    assert first["output_tokens"] == 300
    assert first["total_tokens"] == 330
    assert second["count"] == 1
    assert second["gen_tps_mean"] == second["gen_tps_p50"] == 30.0


def test_bucket_task_rows_omits_empty_buckets():
    """A quiet hour is a gap, not a run of zeroes pulling the chart down."""
    minute = BASE.timestamp()
    rows = [
        {"ts_epoch": minute, "gen_tps": 10.0, "ttft_seconds": 1.0,
         "input_tokens": 1, "output_tokens": 1},
        {"ts_epoch": minute + 600, "gen_tps": 10.0, "ttft_seconds": 1.0,
         "input_tokens": 1, "output_tokens": 1},
    ]

    assert len(bucket_task_rows(rows, 60)) == 2


def test_bucket_task_rows_on_no_rows_is_empty():
    assert bucket_task_rows([], 900) == []


def test_bucket_hardware_rows_means_and_keeps_ram_extremes():
    minute = BASE.timestamp()
    rows = [
        {"ts_epoch": minute, "sample_count": 12, "ram_used_gb": 10.0,
         "ram_total_gb": 32.0, "ram_percent": 30.0, "ram_percent_min": 28.0,
         "ram_percent_max": 34.0, "cpu_percent": 20.0, "swap_used_gb": 0.0,
         "gpu_load_percent": 40.0, "gpu_temp_c": 50.0,
         "temperatures": json.dumps({"k10temp/Tctl": 55.0})},
        {"ts_epoch": minute + 60, "sample_count": 12, "ram_used_gb": 20.0,
         "ram_total_gb": 32.0, "ram_percent": 60.0, "ram_percent_min": 55.0,
         "ram_percent_max": 90.0, "cpu_percent": 40.0, "swap_used_gb": 1.0,
         "gpu_load_percent": 60.0, "gpu_temp_c": 70.0,
         "temperatures": json.dumps({"k10temp/Tctl": 65.0})},
    ]

    buckets = bucket_hardware_rows(rows, 900)

    assert len(buckets) == 1
    bucket = buckets[0]
    assert bucket["count"] == 24
    assert bucket["ram_used_gb"] == 15.0
    assert bucket["ram_percent"] == 45.0
    assert bucket["ram_percent_min"] == 28.0
    assert bucket["ram_percent_max"] == 90.0
    assert bucket["cpu_percent"] == 30.0
    assert bucket["gpu_load_percent"] == 50.0
    assert bucket["temps"] == {"k10temp/Tctl": 60.0}


def test_bucket_hardware_rows_reports_absent_gpu_as_none():
    rows = [
        {"ts_epoch": BASE.timestamp(), "sample_count": 1, "ram_used_gb": 1.0,
         "ram_total_gb": 8.0, "ram_percent": 12.5, "ram_percent_min": 12.5,
         "ram_percent_max": 12.5, "cpu_percent": 5.0, "swap_used_gb": 0.0,
         "gpu_load_percent": None, "gpu_temp_c": None, "temperatures": "{}"},
    ]

    bucket = bucket_hardware_rows(rows, 60)[0]

    assert bucket["gpu_load_percent"] is None
    assert bucket["gpu_temp_c"] is None
    assert bucket["temps"] == {}


def test_resolve_range_maps_selectors_and_falls_back():
    assert resolve_range("1h")[2] == 5 * 60
    assert resolve_range("24h")[2] == 60 * 60
    assert resolve_range("7d")[2] == 6 * 60 * 60
    assert resolve_range("30d")[2] == 24 * 60 * 60
    assert resolve_range("nonsense")[0] == "24h"
    assert resolve_range(None)[0] == "24h"


def test_task_series_runs_end_to_end_through_sqlite(store):
    store.insert_tasks([
        make_row(0, gen_tps=10.0),
        make_row(30, gen_tps=20.0),
        make_row(3600, gen_tps=30.0),
    ])

    buckets = store.task_series(BASE - timedelta(hours=1), BASE + timedelta(hours=2), 3600)

    assert [bucket["count"] for bucket in buckets] == [2, 1]
    assert buckets[0]["gen_tps_mean"] == 15.0
    assert buckets[1]["gen_tps_mean"] == 30.0


# ── Hardware rollups ───────────────────────────────────────


def test_hardware_minute_rows_are_upserted_in_place(store):
    minute = {
        "timestamp": BASE.isoformat(), "sample_count": 4, "ram_used_gb": 10.0,
        "ram_total_gb": 32.0, "ram_percent": 30.0, "ram_percent_min": 29.0,
        "ram_percent_max": 31.0, "cpu_percent": 12.0, "swap_used_gb": 0.0,
        "gpu_load_percent": None, "gpu_temp_c": None, "temperatures": {},
    }
    store.upsert_hardware_minute(minute)
    store.upsert_hardware_minute({**minute, "sample_count": 12, "ram_percent": 40.0})

    buckets = store.hardware_series(BASE - timedelta(minutes=1), BASE + timedelta(minutes=1), 60)

    assert store.count_hardware() == 1
    assert buckets[0]["count"] == 12
    assert buckets[0]["ram_percent"] == 40.0


# ── Retention ──────────────────────────────────────────────


def test_prune_drops_rows_past_their_retention_window(store):
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    fresh = now - timedelta(days=1)
    stale_task = now - timedelta(days=91)
    stale_hardware = now - timedelta(days=31)
    kept_hardware = now - timedelta(days=29)

    store.insert_tasks([
        TaskRow(fresh.isoformat(), "m", 1, 1, 1, 1, 1, 1, "stop", "inferred"),
        TaskRow(stale_task.isoformat(), "m", 1, 1, 1, 1, 1, 1, "stop", "inferred"),
    ])
    for moment in (kept_hardware, stale_hardware):
        store.upsert_hardware_minute({
            "timestamp": moment.isoformat(), "sample_count": 1, "ram_used_gb": 1.0,
            "ram_total_gb": 8.0, "ram_percent": 12.0, "ram_percent_min": 12.0,
            "ram_percent_max": 12.0, "cpu_percent": 1.0, "swap_used_gb": 0.0,
            "gpu_load_percent": None, "gpu_temp_c": None, "temperatures": {},
        })

    removed = store.prune(task_retention_days=90, hardware_retention_days=30, now=now)

    assert removed == {"tasks": 1, "hardware": 1}
    assert store.count_tasks() == 1
    assert store.count_hardware() == 1
    assert store.get_tasks()[0]["timestamp"] == fresh.isoformat()


def _seed_old_rows(store: MetricsStore, now: datetime) -> None:
    store.insert_tasks([
        TaskRow((now - timedelta(days=d)).isoformat(), "m", 1, 1, 1, 1, 1, 1, "stop", "inferred")
        for d in (1, 400)
    ])
    for days in (1, 45):
        store.upsert_hardware_minute({
            "timestamp": (now - timedelta(days=days)).isoformat(), "sample_count": 1,
            "ram_used_gb": 1.0, "ram_total_gb": 8.0, "ram_percent": 12.0,
            "ram_percent_min": 12.0, "ram_percent_max": 12.0, "cpu_percent": 1.0,
            "swap_used_gb": 0.0, "gpu_load_percent": None, "gpu_temp_c": None,
            "temperatures": {},
        })


def test_zero_retention_means_no_limit_not_delete_all(store):
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    _seed_old_rows(store, now)

    removed = store.prune(task_retention_days=0, hardware_retention_days=0, now=now)

    assert removed == {"tasks": 0, "hardware": 0}
    assert store.count_tasks() == 2
    assert store.count_hardware() == 2


def test_default_retention_keeps_tasks_and_prunes_hardware_after_30_days(store):
    from app.config import Settings

    # The shipped defaults, independent of any local .env.
    task_days = Settings.model_fields["task_retention_days"].default
    hardware_days = Settings.model_fields["hardware_retention_days"].default
    assert (task_days, hardware_days) == (0, 30)
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    _seed_old_rows(store, now)

    removed = store.prune(task_days, hardware_days, now=now)

    assert removed == {"tasks": 0, "hardware": 1}
    assert store.count_tasks() == 2


def test_prune_on_an_empty_store_removes_nothing(store):
    assert store.prune(task_retention_days=90, hardware_retention_days=30) == {
        "tasks": 0,
        "hardware": 0,
    }


def test_clear_wipes_both_series(store):
    store.insert_tasks([make_row(0)])
    store.upsert_hardware_minute({
        "timestamp": BASE.isoformat(), "sample_count": 1, "ram_used_gb": 1.0,
        "ram_total_gb": 8.0, "ram_percent": 12.0, "ram_percent_min": 12.0,
        "ram_percent_max": 12.0, "cpu_percent": 1.0, "swap_used_gb": 0.0,
        "gpu_load_percent": None, "gpu_temp_c": None, "temperatures": {},
    })

    store.clear()

    assert store.count_tasks() == 0
    assert store.count_hardware() == 0


def _hardware_minute(moment: datetime) -> dict:
    return {
        "timestamp": moment.isoformat(), "sample_count": 1, "ram_used_gb": 1.0,
        "ram_total_gb": 8.0, "ram_percent": 12.0, "ram_percent_min": 12.0,
        "ram_percent_max": 12.0, "cpu_percent": 1.0, "swap_used_gb": 0.0,
        "gpu_load_percent": None, "gpu_temp_c": None, "temperatures": {},
    }


def test_cleared_tasks_still_in_the_journal_are_not_stored_again(store):
    rows = [make_row(0), make_row(60)]
    store.insert_tasks(rows)

    store.clear(now=BASE + timedelta(minutes=5))

    assert store.insert_tasks(rows) == 0
    assert store.count_tasks() == 0


def test_a_task_completed_after_the_clear_is_stored(store):
    store.insert_tasks([make_row(0)])
    store.clear(now=BASE + timedelta(minutes=5))

    assert store.insert_tasks([make_row(0), make_row(5 * 60), make_row(5 * 60 + 1)]) == 1
    assert [row["timestamp"] for row in store.get_tasks()] == [make_row(5 * 60 + 1).timestamp]


def test_the_clear_time_is_stored_with_the_delete(store):
    store.insert_tasks([make_row(0)])
    moment = BASE + timedelta(minutes=5)

    store.clear(now=moment)

    assert store.get_meta(CLEARED_AT_META_KEY) == moment.isoformat()


def test_a_later_clear_with_an_earlier_clock_keeps_the_later_cut_off(store):
    store.clear(now=BASE + timedelta(minutes=5))
    store.clear(now=BASE)

    assert store.insert_tasks([make_row(60)]) == 0


def test_an_undated_task_is_skipped_once_the_history_was_cleared(store):
    """Its timestamp is only the time it was read, after any cut-off."""
    undated = replace(make_row(10 * 60), dated=False)
    store.clear(now=BASE + timedelta(minutes=5))

    assert store.insert_tasks([undated]) == 0


def test_a_hardware_minute_begun_before_the_clear_is_not_written_again(store):
    """The collector's running aggregate still holds pre-clear samples."""
    store.upsert_hardware_minute(_hardware_minute(BASE))
    store.clear(now=BASE + timedelta(seconds=30))

    store.upsert_hardware_minute(_hardware_minute(BASE))
    assert store.count_hardware() == 0

    store.upsert_hardware_minute(_hardware_minute(BASE + timedelta(minutes=1)))
    assert store.count_hardware() == 1


def test_a_failed_write_leaves_nothing_behind(store):
    store.initialize()

    def half_done(connection):
        connection.execute("DELETE FROM task_records")
        raise RuntimeError("interrupted")

    store.insert_tasks([make_row(0)])
    with pytest.raises(RuntimeError):
        store._write(half_done)

    assert store.count_tasks() == 1


# ── Legacy JSON migration ──────────────────────────────────


def test_legacy_json_history_is_imported_once(tmp_path, store):
    legacy = tmp_path / "task_history.json"
    legacy.write_text(json.dumps({"tasks": [
        {
            "timestamp": BASE.isoformat(), "model": "current",
            "input_tokens": 91, "output_tokens": 61, "prompt_tps": 73.39,
            "gen_tps": 13.84, "ttft_seconds": 1.24, "total_seconds": 5.6,
            "finish_reason": "stop", "finish_confidence": "inferred",
        },
    ]}), encoding="utf-8")
    history = TaskHistory(store)

    assert history.migrate_legacy_json(legacy) == 1
    assert history.migrate_legacy_json(legacy) == 0
    assert store.count_tasks() == 1
    assert legacy.exists()  # The file is left alone.
    assert store.get_meta(MIGRATION_META_KEY) is not None


def test_migration_without_a_legacy_file_is_a_no_op(tmp_path, store):
    history = TaskHistory(store)

    assert history.migrate_legacy_json(tmp_path / "missing.json") == 0
    assert store.count_tasks() == 0


@pytest.mark.parametrize(
    "content",
    [b"{not json", b'{"tasks": "none"}', b"[]", b"\xff\xfe not utf-8"],
    ids=["invalid-json", "tasks-not-a-list", "not-an-object", "not-utf-8"],
)
def test_a_legacy_file_that_cannot_be_read_is_imported_on_a_later_start(
    tmp_path, store, content
):
    """Reported in review: a failed import was marked done and never retried."""
    legacy = tmp_path / "task_history.json"
    legacy.write_bytes(content)
    history = TaskHistory(store)

    with pytest.raises(LegacyHistoryError):
        history.migrate_legacy_json(legacy)
    assert store.get_meta(MIGRATION_META_KEY) is None

    legacy.write_text(json.dumps({"tasks": [_legacy_entry()]}), encoding="utf-8")

    assert history.migrate_legacy_json(legacy) == 1
    assert store.get_meta(MIGRATION_META_KEY) is not None


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="POSIX permissions")
def test_a_legacy_file_that_cannot_be_opened_is_not_marked_imported(tmp_path, store):
    legacy = tmp_path / "task_history.json"
    legacy.write_text(json.dumps({"tasks": [_legacy_entry()]}), encoding="utf-8")
    legacy.chmod(0)
    try:
        with pytest.raises(LegacyHistoryError):
            TaskHistory(store).migrate_legacy_json(legacy)
    finally:
        legacy.chmod(0o600)

    assert store.get_meta(MIGRATION_META_KEY) is None


def test_a_failed_insert_does_not_mark_the_import_done(tmp_path, store, monkeypatch):
    legacy = tmp_path / "task_history.json"
    legacy.write_text(json.dumps({"tasks": [_legacy_entry()]}), encoding="utf-8")

    def unwritable(rows):
        raise sqlite3.OperationalError("attempt to write a readonly database")

    monkeypatch.setattr(store, "insert_tasks", unwritable)

    with pytest.raises(sqlite3.OperationalError):
        TaskHistory(store).migrate_legacy_json(legacy)
    assert store.get_meta(MIGRATION_META_KEY) is None


def _legacy_entry() -> dict:
    return {
        "timestamp": BASE.isoformat(), "model": "current",
        "input_tokens": 91, "output_tokens": 61, "prompt_tps": 73.39,
        "gen_tps": 13.84, "ttft_seconds": 1.24, "total_seconds": 5.6,
        "finish_reason": "stop", "finish_confidence": "inferred",
    }


def test_migration_skips_unusable_legacy_entries(tmp_path, store):
    legacy = tmp_path / "task_history.json"
    legacy.write_text(json.dumps({"tasks": [
        {"model": "current"},  # No timestamp.
        {
            "timestamp": BASE.isoformat(), "model": "current",
            "input_tokens": 1, "output_tokens": 1, "prompt_tps": 1,
            "gen_tps": 1, "ttft_seconds": 1, "total_seconds": 1,
            "finish_reason": "stop", "finish_confidence": "inferred",
        },
    ]}), encoding="utf-8")

    assert TaskHistory(store).migrate_legacy_json(legacy) == 1


def test_legacy_timestamps_are_stored_as_utc_with_one_spelling(tmp_path, store):
    """Early versions wrote naive utcnow() times; others wrote aware ones."""
    legacy = tmp_path / "task_history.json"
    naive = {**_legacy_entry(), "timestamp": "2026-08-22T10:00:00.250000"}
    zulu = {**_legacy_entry(), "timestamp": "2026-08-22T11:00:00Z", "input_tokens": 5}
    legacy.write_text(json.dumps({"tasks": [naive, zulu]}), encoding="utf-8")

    TaskHistory(store).migrate_legacy_json(legacy)

    assert [row["timestamp"] for row in store.get_tasks()] == [
        "2026-08-22T10:00:00.250000+00:00",
        "2026-08-22T11:00:00+00:00",
    ]
    # The same instant from the journal is the same record.
    aware = replace(make_row(0), timestamp="2026-08-22T10:00:00.250000+00:00",
                    model="current")
    assert store.insert_tasks([aware]) == 0


def test_a_legacy_entry_with_an_unreadable_timestamp_is_skipped(tmp_path, store):
    """It used to be stored, dated at the moment of the import."""
    legacy = tmp_path / "task_history.json"
    broken = {**_legacy_entry(), "timestamp": "yesterday"}
    legacy.write_text(json.dumps({"tasks": [broken, _legacy_entry()]}), encoding="utf-8")

    assert TaskHistory(store).migrate_legacy_json(legacy) == 1
    assert [row["timestamp"] for row in store.get_tasks()] == [BASE.isoformat()]


# ── History facade ─────────────────────────────────────────


def test_refresh_from_logs_is_skipped_without_journalctl(store, monkeypatch):
    """A host with no journal must degrade quietly, not raise."""
    monkeypatch.setattr("app.services.metrics.task_history.capabilities.cmd_journalctl", False)

    assert TaskHistory(store).refresh_from_logs() == 0


def test_refresh_from_logs_stores_every_journal_record(store, monkeypatch):
    monkeypatch.setattr("app.services.metrics.task_history.capabilities.cmd_journalctl", True)
    monkeypatch.setattr(
        "app.services.metrics.task_history.parse_task_records",
        lambda **kwargs: extract_task_records(
            FIXTURE.read_text(encoding="utf-8").splitlines()
        ),
    )
    history = TaskHistory(store)

    assert history.refresh_from_logs() == 9
    assert history.refresh_from_logs() == 0


def test_refresh_from_logs_reports_a_broken_journal(store, monkeypatch):
    """The sampler has to see the failure to log it; a read does not."""
    def explode(**kwargs):
        raise JournalReadError("journalctl exited with status 1")

    monkeypatch.setattr("app.services.metrics.task_history.capabilities.cmd_journalctl", True)
    monkeypatch.setattr("app.services.metrics.task_history.parse_task_records", explode)
    store.insert_tasks([make_row(0)])
    history = TaskHistory(store)

    with pytest.raises(JournalReadError):
        history.refresh_from_logs()
    # The read endpoints still serve what is stored.
    assert len(history.get_recent()) == 1
    assert history.export_csv().count("\n") == 2


def test_export_csv_carries_a_header_even_when_empty(store):
    body = TaskHistory(store).export_csv(refresh=False)

    assert body.splitlines()[0] == (
        "timestamp,model,input_tokens,output_tokens,prompt_tps,gen_tps,"
        "ttft_seconds,total_seconds,finish_reason,finish_confidence"
    )
    assert len(body.splitlines()) == 1


def test_export_csv_honours_the_window(store):
    store.insert_tasks([make_row(0), make_row(3600)])

    body = TaskHistory(store).export_csv(
        since=BASE + timedelta(minutes=30), refresh=False
    )

    assert len(body.splitlines()) == 2


# ── Window summary ─────────────────────────────────────────


def test_summarize_task_rows_uses_the_raw_values_not_bucket_percentiles(store):
    """A window p95 has to come from the runs, not from averaged bucket p95s."""
    store.insert_tasks([
        make_row(offset, gen_tps=float(n + 1))
        for n, offset in enumerate(range(0, 100 * 60, 60))
    ])

    window = store.task_window(BASE - timedelta(hours=1), BASE + timedelta(days=1), 3600)

    assert window["summary"]["count"] == 100
    assert window["summary"]["gen_tps_p50"] == 50.0
    assert window["summary"]["gen_tps_p95"] == 95.0
    assert window["summary"]["gen_tps_mean"] == 50.5
    assert sum(bucket["count"] for bucket in window["buckets"]) == 100


def test_task_window_summary_is_zeroed_on_an_empty_window(store):
    window = store.task_window(BASE, BASE + timedelta(hours=1), 3600)

    assert window["buckets"] == []
    assert window["summary"] == {
        "count": 0,
        "gen_tps_mean": 0.0,
        "gen_tps_p50": 0.0,
        "gen_tps_p95": 0.0,
        "ttft_mean": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def test_stored_finish_confidence_matches_the_rest_of_the_api(store):
    """Plain "inferred", not the enum's repr, so CSV exports stay readable."""
    history = TaskHistory(store)
    history.ingest(extract_task_records([
        ("2026-08-22 10:11:15.874 [Info] (Telemetry) Inference completed: "
        "model=Gemma-4-12B-it-MTP-GGUF, tokens=152 (in=91, out=61), "
        "ttft=1.24s, tps=13.84"),
    ]))

    row = store.get_tasks()[0]

    assert row["finish_reason"] == "stop"
    assert row["finish_confidence"] == "inferred"


# ── Unmeasurable generation rates ──────────────────────────


def test_single_token_completion_has_no_measurable_rate():
    """Lemonade reports 1000000.0 t/s when there is no generation interval."""
    assert measurable_rate(1000000.0, output_tokens=1) == 0.0
    assert measurable_rate(29.3, output_tokens=1) == 0.0


def test_implausible_or_broken_rates_are_rejected():
    assert measurable_rate(1000000.0, output_tokens=50) == 0.0
    assert measurable_rate(float("nan"), output_tokens=50) == 0.0
    assert measurable_rate(float("inf"), output_tokens=50) == 0.0
    assert measurable_rate(-1.0, output_tokens=50) == 0.0
    assert measurable_rate("nonsense", output_tokens=50) == 0.0


def test_real_rates_pass_through_untouched():
    assert measurable_rate(29.3, output_tokens=61) == 29.3
    assert measurable_rate(15.45, output_tokens=284) == 15.45


def test_sentinel_rate_is_never_stored(store):
    store.insert_tasks([make_row(0, gen_tps=1000000.0, output_tokens=1)])

    [row] = store.get_tasks()
    assert row["gen_tps"] == 0.0
    assert row["output_tokens"] == 1


def test_sentinel_row_is_kept_as_a_run_but_not_as_a_speed(store):
    """The run happened and its ttft is real; only the rate is meaningless."""
    store.insert_tasks([
        make_row(0, gen_tps=20.0),
        make_row(60, gen_tps=30.0),
        make_row(120, gen_tps=1000000.0, output_tokens=1),
    ])

    window = store.task_window(BASE - timedelta(hours=1), BASE + timedelta(days=1), 3600)
    summary = window["summary"]
    [bucket] = window["buckets"]

    assert summary["count"] == 3, "the run must still be counted"
    assert summary["gen_tps_mean"] == 25.0, "the sentinel must not drag the mean"
    assert summary["gen_tps_p95"] == 30.0
    assert bucket["count"] == 3
    assert bucket["gen_tps_mean"] == 25.0
    assert bucket["gen_tps_p95"] == 30.0


def test_legacy_import_drops_the_sentinel_rate(tmp_path, store):
    legacy = tmp_path / "task_history.json"
    legacy.write_text(json.dumps({"tasks": [
        {
            "timestamp": BASE.isoformat(), "model": "current",
            "input_tokens": 15893, "output_tokens": 1, "prompt_tps": 900.0,
            "gen_tps": 1000000.0, "ttft_seconds": 17.6, "total_seconds": 17.6,
            "finish_reason": "length", "finish_confidence": "inferred",
        },
    ]}), encoding="utf-8")

    assert TaskHistory(store).migrate_legacy_json(legacy) == 1

    [row] = store.get_tasks()
    assert row["gen_tps"] == 0.0
    assert row["ttft_seconds"] == 17.6
