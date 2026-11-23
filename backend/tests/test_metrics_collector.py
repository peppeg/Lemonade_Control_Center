import asyncio
import json
import logging
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
    for failure_log in collector.FAILURE_LOGS:
        failure_log.reset()
    yield replacement
    task_history.use_store(original)
    collector._minute = None
    collector.buffer.clear()
    for failure_log in collector.FAILURE_LOGS:
        failure_log.reset()


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

    row = store.get_hardware_minute(MINUTE)

    assert store.count_hardware() == 1
    assert row["timestamp"] == MINUTE.isoformat()
    assert row["sample_count"] == 3
    assert row["ram_percent"] == 40.0     # mean of the minute
    assert row["ram_percent_min"] == 30.0
    assert row["ram_percent_max"] == 50.0


@pytest.mark.asyncio
async def test_a_new_minute_starts_a_new_row(store):
    await collector._persist_minute(point(10, 30.0))
    await collector._persist_minute(point(70, 60.0))

    assert store.count_hardware() == 2


@pytest.mark.asyncio
async def test_a_restart_mid_minute_keeps_the_samples_already_stored(store):
    """A restart used to replace the minute's row with the samples after it."""
    for seconds in (0, 5, 10, 15, 20):
        sample = point(seconds, 90.0, cpu=10.0)
        sample.gpu_gtt_used_gb = 40.0
        await collector._persist_minute(sample)
    collector._minute = None  # What a restart leaves behind.

    await collector._persist_minute(point(30, 30.0, cpu=40.0))

    row = store.get_hardware_minute(MINUTE)
    assert row["sample_count"] == 6
    assert row["ram_percent"] == pytest.approx(80.0)   # (5 x 90 + 30) / 6
    assert row["ram_percent_min"] == 30.0
    assert row["ram_percent_max"] == 90.0
    assert row["cpu_percent"] == pytest.approx(15.0)   # (5 x 10 + 40) / 6
    assert row["gpu_gtt_used_gb"] == 40.0      # Kept, though the new sample has none.
    assert json.loads(row["temperatures"]) == {"k10temp/Tctl": 65.0}


@pytest.mark.asyncio
async def test_the_rollup_keeps_the_temperature_dictionary(store):
    await collector._persist_minute(point(0, 30.0, cpu=10.0))
    await collector._persist_minute(point(5, 30.0, cpu=20.0))

    row = store.get_hardware_minute(MINUTE)

    assert json.loads(row["temperatures"]) == {"k10temp/Tctl": 65.0}


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


# ── Failure logging ────────────────────────────────────────


def _warnings(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == collector.log.name and record.levelno == logging.WARNING
    ]


def test_failure_log_warns_once_then_at_most_once_per_interval(caplog):
    now = {"t": 0.0}
    failure_log = collector.FailureLog("Job", interval_seconds=600, clock=lambda: now["t"])

    with caplog.at_level(logging.WARNING, logger=collector.log.name):
        failure_log.failed(RuntimeError("readonly database"))
        for seconds in (15, 30, 599):
            now["t"] = seconds
            failure_log.failed(RuntimeError("readonly database"))
        now["t"] = 600
        failure_log.failed(RuntimeError("readonly database"))

    assert _warnings(caplog) == [
        "Job failed: readonly database",
        "Job still failing (5 failures so far): readonly database",
    ]


def test_failure_log_reports_recovery_once(caplog):
    failure_log = collector.FailureLog("Job", clock=lambda: 0.0)

    with caplog.at_level(logging.WARNING, logger=collector.log.name):
        failure_log.succeeded()  # Nothing failed: nothing to say.
        failure_log.failed(RuntimeError("readonly database"))
        failure_log.failed(RuntimeError("readonly database"))
        failure_log.succeeded()
        failure_log.succeeded()
        failure_log.failed(RuntimeError("readonly database"))

    assert _warnings(caplog) == [
        "Job failed: readonly database",
        "Job recovered after 2 failures",
        "Job failed: readonly database",
    ]


@pytest.mark.asyncio
async def test_an_unwritable_store_is_logged_not_swallowed(store, monkeypatch, caplog):
    def explode(_row):
        raise RuntimeError("attempt to write a readonly database")

    monkeypatch.setattr(store, "upsert_hardware_minute", explode)

    with caplog.at_level(logging.WARNING, logger=collector.log.name):
        for seconds in (0, 5, 10):
            await collector._persist_minute(point(seconds, 30.0))
        monkeypatch.undo()
        task_history.use_store(store)
        await collector._persist_minute(point(15, 30.0))

    assert _warnings(caplog) == [
        "Hardware history write failed: attempt to write a readonly database",
        "Hardware history write recovered after 3 failures",
    ]


@pytest.mark.asyncio
async def test_task_sampler_and_pruner_failures_are_logged(store, monkeypatch, caplog):
    def explode(*args, **kwargs):
        raise RuntimeError("disk I/O error")

    monkeypatch.setattr(task_history, "refresh_from_logs", explode)
    monkeypatch.setattr(store, "prune", explode)

    with caplog.at_level(logging.WARNING, logger=collector.log.name):
        await collector.sample_tasks_once()
        await collector.sample_tasks_once()
        await collector.prune_once()

    assert _warnings(caplog) == [
        "Task history sampling failed: disk I/O error",
        "Metrics history pruning failed: disk I/O error",
    ]


@pytest.mark.asyncio
async def test_the_rollup_keeps_gpu_memory_when_the_host_reports_it(store):
    for seconds, gtt in ((0, 40.0), (5, 44.0)):
        sample = point(seconds, 30.0)
        sample.gpu_vram_used_gb = 0.5
        sample.gpu_gtt_used_gb = gtt
        await collector._persist_minute(sample)
    await collector._persist_minute(point(65, 30.0))  # Next minute: not reported.

    first = store.get_hardware_minute(MINUTE)
    second = store.get_hardware_minute(MINUTE + timedelta(minutes=1))

    assert first["gpu_vram_used_gb"] == 0.5
    assert first["gpu_gtt_used_gb"] == 42.0
    assert second["gpu_vram_used_gb"] is None
    assert second["gpu_gtt_used_gb"] is None


@pytest.mark.asyncio
async def test_an_unreadable_journal_is_logged_by_the_task_sampler(store, monkeypatch, caplog):
    """Reported in review: the sampler counted an unreadable journal as success."""
    from types import SimpleNamespace

    from app.services.metrics import task_history as task_history_module

    monkeypatch.setattr(task_history_module.capabilities, "cmd_journalctl", True)
    monkeypatch.setattr(
        "app.services.log_parser.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="No journal files were opened due to insufficient permissions.\n",
        ),
    )

    with caplog.at_level(logging.WARNING, logger=collector.log.name):
        assert await collector.sample_tasks_once() == 0

    assert _warnings(caplog) == [
        (
            "Task history sampling failed: journalctl exited with status 1: "
            "No journal files were opened due to insufficient permissions."
        ),
    ]
    assert collector.task_sampler_failures.failures == 1


@pytest.mark.asyncio
async def test_a_failed_legacy_import_is_logged_once_per_start(store, monkeypatch, caplog, tmp_path):
    legacy = tmp_path / "task_history.json"
    legacy.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr("app.services.metrics.task_history.HISTORY_FILE", legacy)

    with caplog.at_level(logging.WARNING, logger=collector.log.name):
        await collector.import_legacy_history()

    [warning] = _warnings(caplog)
    assert warning.startswith("Import of task_history.json failed: cannot read")
    assert store.get_meta("task_history_json_imported") is None



@pytest.mark.asyncio
async def test_start_imports_once_then_samples_tasks_one_at_a_time(store, monkeypatch):
    """The start-up sample used to run alongside the sampler loop's first tick."""
    events: list[str] = []
    running = 0
    overlaps = 0

    def migrate():
        events.append("import")

    async def sample():
        nonlocal running, overlaps
        running += 1
        overlaps = max(overlaps, running)
        events.append("sample")
        await asyncio.sleep(0.05)
        running -= 1
        return 0

    async def idle(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(task_history, "migrate_legacy_json", migrate)
    monkeypatch.setattr(collector, "sample_tasks_once", sample)
    monkeypatch.setattr(collector, "_collector_loop", idle)
    monkeypatch.setattr(collector, "_pruner_loop", idle)
    before = asyncio.all_tasks()

    collector.start_collector()
    await asyncio.sleep(0.2)
    collector.stop_collector()
    await asyncio.sleep(0)

    assert events == ["import", "sample"]
    assert overlaps == 1
    # Nothing started by the collector outlives stop_collector().
    assert all(task.done() for task in asyncio.all_tasks() - before - {asyncio.current_task()})


@pytest.mark.asyncio
async def test_subscribers_get_a_sample_before_it_is_written_to_the_history(store, monkeypatch):
    """Reported in review: a locked database held the live charts for up to
    the connection timeout, because the write came first."""
    import threading

    release = threading.Event()
    written: list[dict] = []

    def slow_upsert(row):
        release.wait(5)
        written.append(row)

    monkeypatch.setattr(store, "upsert_hardware_minute", slow_upsert)
    monkeypatch.setattr(collector, "_sample", lambda: point(0, 30.0))
    queue = collector.subscribe()
    try:
        running = asyncio.create_task(collector.collect_once())
        latest = await asyncio.wait_for(queue.get(), timeout=2)

        assert latest["ram_pct"] == 30.0
        assert written == []  # The write is still waiting.
        release.set()
        await running
        assert len(written) == 1
    finally:
        release.set()
        collector.unsubscribe(queue)


@pytest.mark.asyncio
async def test_a_failure_anywhere_in_the_rollup_leaves_the_live_sample_alone(store, monkeypatch, caplog):
    def broken_add(self, sample):
        raise ValueError("bad sample")

    monkeypatch.setattr(collector._MinuteAggregate, "add", broken_add)
    monkeypatch.setattr(collector, "_sample", lambda: point(0, 30.0))
    queue = collector.subscribe()
    try:
        with caplog.at_level(logging.WARNING, logger=collector.log.name):
            latest = await collector.collect_once()
    finally:
        collector.unsubscribe(queue)

    assert latest["ram_pct"] == 30.0
    assert queue.get_nowait()["ram_pct"] == 30.0
    assert collector.rollup_failures.failures == 1
    assert "Hardware history write failed" in caplog.text


@pytest.mark.asyncio
async def test_the_live_samples_keep_their_interval_when_a_write_is_slow(monkeypatch):
    sleeps: list[float] = []
    clock = [100.0]

    async def slow_collect():
        clock[0] += 3.0  # A write held by a locked database.
        return {}

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        raise asyncio.CancelledError

    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "time", lambda: clock[0])
    monkeypatch.setattr(collector, "collect_once", slow_collect)
    monkeypatch.setattr(collector.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await collector._collector_loop(10)

    assert sleeps == [7.0]
