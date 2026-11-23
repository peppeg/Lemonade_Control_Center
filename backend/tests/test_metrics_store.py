import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.log_parser import extract_task_records
from app.services.metrics.store import (
    MetricsStore,
    TaskRow,
    bucket_hardware_rows,
    bucket_start,
    bucket_task_rows,
    measurable_rate,
    percentile,
    resolve_range,
)
from app.services.metrics.task_history import MIGRATION_META_KEY, TaskHistory

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


def test_migration_survives_a_corrupt_legacy_file(tmp_path, store):
    legacy = tmp_path / "task_history.json"
    legacy.write_text("{not json", encoding="utf-8")
    history = TaskHistory(store)

    assert history.migrate_legacy_json(legacy) == 0
    assert store.count_tasks() == 0


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


def test_refresh_from_logs_swallows_a_broken_journal(store, monkeypatch):
    def explode(**kwargs):
        raise RuntimeError("journal exploded")

    monkeypatch.setattr("app.services.metrics.task_history.capabilities.cmd_journalctl", True)
    monkeypatch.setattr("app.services.metrics.task_history.parse_task_records", explode)

    assert TaskHistory(store).refresh_from_logs() == 0


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
