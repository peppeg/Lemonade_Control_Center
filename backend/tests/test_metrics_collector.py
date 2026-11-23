from datetime import UTC, datetime, timedelta

import pytest

from app.services.metrics import collector
from app.services.metrics.buffer import DataPoint
from app.services.metrics.store import MetricsStore
from app.services.metrics.task_history import task_history

MINUTE = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path):
    """Give the collector a throwaway database and a clean minute accumulator."""
    original = task_history.store
    replacement = MetricsStore(tmp_path / "lcc_metrics.db")
    task_history.use_store(replacement)
    collector._minute = None
    collector.buffer.clear()
    yield replacement
    task_history.use_store(original)
    collector._minute = None
    collector.buffer.clear()


def point(seconds: float, ram_percent: float, cpu: float = 10.0) -> DataPoint:
    return DataPoint(
        timestamp=MINUTE + timedelta(seconds=seconds),
        ram_used_gb=ram_percent / 100 * 32,
        ram_total_gb=32.0,
        ram_percent=ram_percent,
        cpu_percent=cpu,
        swap_used_gb=0.0,
        gpu_load_percent=None,
        gpu_temp_c=None,
        temperatures={"k10temp/Tctl": 50.0 + cpu},
    )


@pytest.mark.asyncio
async def test_samples_in_one_minute_collapse_to_a_single_row(store):
    for seconds, ram in ((0, 30.0), (5, 50.0), (10, 40.0)):
        await collector._persist_minute(point(seconds, ram))

    buckets = store.hardware_series(MINUTE, MINUTE + timedelta(minutes=1), 60)

    assert store.count_hardware() == 1
    assert len(buckets) == 1
    assert buckets[0]["t"] == MINUTE.isoformat()
    assert buckets[0]["count"] == 3
    assert buckets[0]["ram_percent"] == 40.0     # mean of the minute
    assert buckets[0]["ram_percent_min"] == 30.0
    assert buckets[0]["ram_percent_max"] == 50.0


@pytest.mark.asyncio
async def test_a_new_minute_starts_a_new_row(store):
    await collector._persist_minute(point(10, 30.0))
    await collector._persist_minute(point(70, 60.0))

    assert store.count_hardware() == 2


@pytest.mark.asyncio
async def test_the_rollup_keeps_the_temperature_dictionary(store):
    await collector._persist_minute(point(0, 30.0, cpu=10.0))
    await collector._persist_minute(point(5, 30.0, cpu=20.0))

    bucket = store.hardware_series(MINUTE, MINUTE + timedelta(minutes=1), 60)[0]

    assert bucket["temps"] == {"k10temp/Tctl": 65.0}


@pytest.mark.asyncio
async def test_a_failing_store_never_breaks_the_live_stream(store, monkeypatch):
    def explode(_row):
        raise RuntimeError("disk full")

    monkeypatch.setattr(store, "upsert_hardware_minute", explode)

    await collector._persist_minute(point(0, 30.0))  # Must not raise.


@pytest.mark.asyncio
async def test_the_task_sampler_records_without_a_ui_connected(store, monkeypatch):
    """R2: history accrues from the background loop, not from frontend polls."""
    calls = {"count": 0}

    def fake_refresh():
        calls["count"] += 1
        return 4

    monkeypatch.setattr(task_history, "refresh_from_logs", fake_refresh)

    assert await collector.sample_tasks_once() == 4
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_the_task_sampler_swallows_journal_failures(store, monkeypatch):
    def explode():
        raise RuntimeError("journalctl gone")

    monkeypatch.setattr(task_history, "refresh_from_logs", explode)

    assert await collector.sample_tasks_once() == 0


@pytest.mark.asyncio
async def test_prune_once_applies_the_configured_retention(store, monkeypatch):
    monkeypatch.setattr("app.services.metrics.collector.settings.task_retention_days", 90)
    monkeypatch.setattr("app.services.metrics.collector.settings.hardware_retention_days", 30)
    stale = datetime.now(UTC) - timedelta(days=120)
    store.upsert_hardware_minute({
        "timestamp": stale.isoformat(), "sample_count": 1, "ram_used_gb": 1.0,
        "ram_total_gb": 8.0, "ram_percent": 12.0, "ram_percent_min": 12.0,
        "ram_percent_max": 12.0, "cpu_percent": 1.0, "swap_used_gb": 0.0,
        "gpu_load_percent": None, "gpu_temp_c": None, "temperatures": {},
    })

    assert await collector.prune_once() == {"tasks": 0, "hardware": 1}
    assert store.count_hardware() == 0


@pytest.mark.asyncio
async def test_prune_once_reports_nothing_removed_when_the_store_fails(store, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("locked")

    monkeypatch.setattr(store, "prune", explode)

    assert await collector.prune_once() == {"tasks": 0, "hardware": 0}
