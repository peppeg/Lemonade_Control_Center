import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.routers.metrics import (
    clear_metrics,
    export_tasks_csv,
    get_hardware_series,
    get_history_summary,
    get_tasks,
    get_tasks_scale,
    get_tasks_series,
)
from app.services.metrics.store import MetricsStore, TaskRow, percentile, resolve_range
from app.services.metrics.task_history import task_history


@pytest.fixture
def empty_store(tmp_path, monkeypatch):
    """Point the shared history at a throwaway database for one test."""
    original = task_history.store
    store = MetricsStore(tmp_path / "lcc_metrics.db")
    task_history.use_store(store)
    # No journal means no ingestion side effects on read endpoints.
    monkeypatch.setattr(
        "app.services.metrics.task_history.capabilities.cmd_journalctl", False
    )
    yield store
    task_history.use_store(original)


def recent_row(minutes_ago: float, gen_tps: float, ttft: float = 1.0) -> TaskRow:
    moment = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return TaskRow(
        timestamp=moment.isoformat(),
        model="Gemma-4-12B-it-MTP-GGUF",
        input_tokens=91,
        output_tokens=61,
        prompt_tps=73.39,
        gen_tps=gen_tps,
        ttft_seconds=ttft,
        total_seconds=5.6,
        finish_reason="stop",
        finish_confidence="inferred",
    )


def sized_row(index: int, output_tokens: int, minutes_ago: float = 5) -> TaskRow:
    """A row whose output_tokens matter and whose identity stays unique.

    The store dedupes on (timestamp, model, in, out), so the index walks the
    timestamp apart -- otherwise two runs of the same size collapse into one.
    """
    moment = datetime.now(UTC) - timedelta(minutes=minutes_ago, seconds=index)
    return TaskRow(
        timestamp=moment.isoformat(),
        model="Gemma-4-12B-it-MTP-GGUF",
        input_tokens=91,
        output_tokens=output_tokens,
        prompt_tps=73.39,
        gen_tps=13.84,
        ttft_seconds=1.0,
        total_seconds=5.6,
        finish_reason="stop",
        finish_confidence="inferred",
    )


def hardware_minute(minutes_ago: float) -> dict:
    minute = (
        datetime.now(UTC) - timedelta(minutes=minutes_ago)
    ).replace(second=0, microsecond=0)
    return {
        "timestamp": minute.isoformat(), "sample_count": 12, "ram_used_gb": 10.0,
        "ram_total_gb": 32.0, "ram_percent": 31.25, "ram_percent_min": 30.0,
        "ram_percent_max": 33.0, "cpu_percent": 18.0, "swap_used_gb": 0.0,
        "gpu_load_percent": 42.0, "gpu_temp_c": 61.0,
        "temperatures": {"k10temp/Tctl": 55.0},
    }


# ── Empty database ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_tasks_endpoint_on_an_empty_database(empty_store):
    assert await get_tasks(n=100, since=None, until=None) == {"tasks": []}


@pytest.mark.asyncio
async def test_tasks_series_endpoint_on_an_empty_database(empty_store):
    for window in ("1h", "24h", "7d", "30d"):
        payload = await get_tasks_series(range=window)

        assert payload["range"] == window
        assert payload["buckets"] == []
        assert payload["start"] < payload["end"]


@pytest.mark.asyncio
async def test_hardware_series_endpoint_on_an_empty_database(empty_store):
    for window in ("1h", "24h", "7d", "30d"):
        payload = await get_hardware_series(range=window)

        assert payload["range"] == window
        assert payload["buckets"] == []


@pytest.mark.asyncio
async def test_tasks_csv_endpoint_on_an_empty_database(empty_store):
    response = await export_tasks_csv(since=None, until=None, range=None)

    assert response.status_code == 200
    assert response.media_type == "text/csv"
    assert (await _csv_text(response)).strip() == (
        "timestamp,model,input_tokens,output_tokens,prompt_tps,gen_tps,"
        "ttft_seconds,total_seconds,finish_reason,finish_confidence"
    )


# ── Populated database ─────────────────────────────────────


@pytest.mark.asyncio
async def test_tasks_endpoint_keeps_its_response_shape(empty_store):
    empty_store.insert_tasks([recent_row(5, 13.84)])

    payload = await get_tasks(n=20, since=None, until=None)

    assert set(payload) == {"tasks"}
    assert set(payload["tasks"][0]) == {
        "timestamp", "model", "input_tokens", "output_tokens", "prompt_tps",
        "gen_tps", "ttft_seconds", "total_seconds", "finish_reason",
        "finish_confidence",
    }


@pytest.mark.asyncio
async def test_tasks_endpoint_honours_since_and_until(empty_store):
    empty_store.insert_tasks([recent_row(120, 10.0), recent_row(5, 20.0)])
    cutoff = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()

    payload = await get_tasks(n=100, since=cutoff, until=None)

    assert [task["gen_tps"] for task in payload["tasks"]] == [20.0]


@pytest.mark.asyncio
async def test_tasks_endpoint_rejects_a_malformed_boundary(empty_store):
    with pytest.raises(HTTPException) as raised:
        await get_tasks(n=10, since="not-a-timestamp", until=None)

    assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_tasks_series_aggregates_recorded_runs(empty_store):
    empty_store.insert_tasks([
        recent_row(3, 10.0, ttft=1.0),
        recent_row(2, 20.0, ttft=3.0),
    ])

    payload = await get_tasks_series(range="1h")

    assert payload["bucket_seconds"] == resolve_range("1h")[2]
    assert sum(bucket["count"] for bucket in payload["buckets"]) == 2
    assert all(bucket["gen_tps_p95"] >= bucket["gen_tps_p50"] for bucket in payload["buckets"])


@pytest.mark.asyncio
async def test_tasks_series_buckets_carry_every_aggregate(empty_store):
    # Anchor both runs inside one bucket so the assertion below does not depend
    # on where "now" happens to sit relative to a bucket boundary.
    bucket = resolve_range("24h")[2]
    anchor = datetime.now(UTC) - timedelta(minutes=5)
    floor = anchor - timedelta(
        seconds=anchor.timestamp() % bucket, microseconds=anchor.microsecond
    )
    minutes_ago = (datetime.now(UTC) - floor).total_seconds() / 60
    empty_store.insert_tasks([
        recent_row(minutes_ago - 1 / 60, 10.0),
        recent_row(minutes_ago - 2 / 60, 20.0),
    ])

    bucket = (await get_tasks_series(range="24h"))["buckets"][0]

    assert set(bucket) == {
        "t", "count", "gen_tps_mean", "gen_tps_p50", "gen_tps_p95",
        "ttft_mean", "input_tokens", "output_tokens", "total_tokens",
    }
    assert bucket["gen_tps_mean"] == 15.0
    assert bucket["total_tokens"] == 304


@pytest.mark.asyncio
async def test_series_uses_the_default_range_when_none_is_given(empty_store):
    assert (await get_tasks_series(range=""))["range"] == "24h"
    assert (await get_hardware_series(range=""))["range"] == "24h"


@pytest.mark.asyncio
async def test_hardware_series_reads_the_persisted_rollups(empty_store):
    minute = (
        datetime.now(UTC) - timedelta(minutes=3)
    ).replace(second=0, microsecond=0)
    empty_store.upsert_hardware_minute({
        "timestamp": minute.isoformat(), "sample_count": 12, "ram_used_gb": 10.0,
        "ram_total_gb": 32.0, "ram_percent": 31.25, "ram_percent_min": 30.0,
        "ram_percent_max": 33.0, "cpu_percent": 18.0, "swap_used_gb": 0.0,
        "gpu_load_percent": 42.0, "gpu_temp_c": 61.0,
        "temperatures": {"k10temp/Tctl": 55.0},
    })

    payload = await get_hardware_series(range="1h")

    assert len(payload["buckets"]) == 1
    bucket = payload["buckets"][0]
    assert bucket["count"] == 12
    assert bucket["ram_percent_max"] == 33.0
    assert bucket["temps"] == {"k10temp/Tctl": 55.0}


@pytest.mark.asyncio
async def test_tasks_csv_honours_the_range_parameter(empty_store):
    empty_store.insert_tasks([recent_row(60 * 40, 10.0), recent_row(5, 20.0)])

    everything = await export_tasks_csv(since=None, until=None, range="7d")
    last_hour = await export_tasks_csv(since=None, until=None, range="1h")

    assert len((await _csv_text(everything)).strip().splitlines()) == 3
    assert len((await _csv_text(last_hour)).strip().splitlines()) == 2


@pytest.mark.asyncio
async def test_tasks_csv_exports_every_row_however_many_there_are(empty_store):
    """It stopped at the newest 100,000 rows, dropping the oldest silently."""
    total = 100_001
    first = datetime.now(UTC) - timedelta(days=3)
    empty_store.initialize()
    connection = sqlite3.connect(empty_store.path)
    with connection:
        connection.executemany(
            "INSERT INTO task_records (timestamp, ts_epoch, model, input_tokens,"
            " output_tokens) VALUES (?, ?, 'm', 1, 1)",
            (
                ((first + timedelta(seconds=index)).isoformat(), first.timestamp() + index)
                for index in range(total)
            ),
        )
    connection.close()

    lines = (await _csv_text(await export_tasks_csv(since=None, until=None, range=None))).splitlines()

    assert len(lines) == total + 1
    assert lines[1].startswith(first.isoformat())


async def _csv_text(response) -> str:
    return "".join([chunk async for chunk in response.body_iterator])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        lambda: get_tasks_series(range="90d"),
        lambda: get_tasks_scale(range="90d", quantile=0.95),
        lambda: get_hardware_series(range="90d"),
        lambda: export_tasks_csv(since=None, until=None, range="90d"),
        lambda: export_tasks_csv(since="2026-08-22T10:00:00Z", until=None, range="90d"),
    ],
    ids=["tasks-series", "tasks-scale", "hardware-series", "csv", "csv-with-since"],
)
async def test_an_unknown_range_is_rejected_not_replaced_by_24h(empty_store, call):
    with pytest.raises(HTTPException) as raised:
        await call()

    assert raised.value.status_code == 400
    assert "1h, 24h, 7d, 30d" in raised.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("bound", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00", "soon"])
async def test_a_bound_outside_the_calendar_is_a_bad_request(empty_store, bound):
    for call in (
        lambda: get_tasks(n=10, since=bound, until=None),
        lambda: get_tasks(n=10, since=None, until=bound),
        lambda: export_tasks_csv(since=bound, until=None, range=None),
    ):
        with pytest.raises(HTTPException) as raised:
            await call()
        assert raised.value.status_code == 400


# ── Clear scopes (R5) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_without_a_scope_is_rejected_not_obeyed(empty_store):
    empty_store.insert_tasks([recent_row(5, 13.84)])

    with pytest.raises(HTTPException) as raised:
        await clear_metrics(scope=None)

    assert raised.value.status_code == 400
    # The point of the rejection: the history survives it.
    assert empty_store.count_tasks() == 1


@pytest.mark.asyncio
async def test_clear_with_an_unknown_scope_is_rejected(empty_store):
    empty_store.insert_tasks([recent_row(5, 13.84)])

    with pytest.raises(HTTPException) as raised:
        await clear_metrics(scope="everything")

    assert raised.value.status_code == 400
    assert empty_store.count_tasks() == 1


@pytest.mark.asyncio
async def test_clear_buffer_scope_leaves_the_persisted_history_intact(empty_store):
    empty_store.insert_tasks([recent_row(5, 13.84)])
    empty_store.upsert_hardware_minute(hardware_minute(3))

    assert await clear_metrics(scope="buffer") == {"cleared": True, "scope": "buffer"}
    assert empty_store.count_tasks() == 1
    assert empty_store.count_hardware() == 1


@pytest.mark.asyncio
async def test_clear_history_scope_deletes_and_reports_both_tables(empty_store):
    empty_store.insert_tasks([recent_row(5, 13.84), recent_row(9, 20.1)])
    empty_store.upsert_hardware_minute(hardware_minute(3))

    payload = await clear_metrics(scope="history")

    assert payload == {
        "cleared": True,
        "scope": "history",
        "deleted": {"tasks": 2, "hardware": 1},
    }
    assert empty_store.count_tasks() == 0
    assert empty_store.count_hardware() == 0


@pytest.mark.asyncio
async def test_cleared_history_stays_cleared_when_tasks_are_read_again(empty_store, monkeypatch):
    """The read endpoints refresh from the journal, which still holds the tasks."""
    from app.services.log_parser import TaskJournalRead, TaskTelemetryRecord

    moment = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    record = TaskTelemetryRecord(
        timestamp=moment, model="m", input_tokens=4, output_tokens=7, ttft_seconds=0.08,
        generation_tps=32.28, prompt_eval_tps=50.0, total_duration_seconds=0.3,
    )
    monkeypatch.setattr(
        "app.services.metrics.task_history.capabilities.cmd_journalctl", True
    )
    monkeypatch.setattr(
        "app.services.metrics.task_history.read_task_journal",
        lambda **_: TaskJournalRead([record]),
    )
    assert len((await get_tasks(n=100, since=None, until=None))["tasks"]) == 1

    payload = await clear_metrics(scope="history")

    assert payload["deleted"]["tasks"] == 1
    assert (await get_tasks(n=100, since=None, until=None))["tasks"] == []


@pytest.mark.asyncio
async def test_history_summary_reports_counts_and_the_oldest_record(empty_store):
    oldest = recent_row(90, 20.1)
    empty_store.insert_tasks([recent_row(5, 13.84), oldest])
    empty_store.upsert_hardware_minute(hardware_minute(3))

    summary = await get_history_summary()

    assert summary["tasks"] == 2
    assert summary["hardware"] == 1
    # The oldest row, not the newest: the confirmation states how far back the
    # delete reaches.
    assert summary["oldest_task"] == oldest.timestamp
    assert summary["oldest_hardware"] is not None


@pytest.mark.asyncio
async def test_history_summary_on_an_empty_database(empty_store):
    assert await get_history_summary() == {
        "tasks": 0,
        "hardware": 0,
        "oldest_task": None,
        "oldest_hardware": None,
    }


# ── Size-scale ceiling (R2) ────────────────────────────────


@pytest.mark.asyncio
async def test_tasks_scale_returns_the_output_token_percentile(empty_store):
    empty_store.insert_tasks(
        [sized_row(index, output_tokens=tokens)
         for index, tokens in enumerate([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], start=1)]
    )

    payload = await get_tasks_scale(range="30d", quantile=0.95)

    assert payload["range"] == "30d"
    assert payload["count"] == 10
    # Nearest-rank over ten values: ceil(0.95 * 10) = 10th, the largest.
    assert payload["output_tokens"] == 100.0


@pytest.mark.asyncio
async def test_tasks_scale_matches_the_stores_own_percentile(empty_store):
    tokens = [7, 91, 140, 512, 3, 1024, 61, 88, 233, 47, 900, 12]
    empty_store.insert_tasks(
        [sized_row(index, output_tokens=value) for index, value in enumerate(tokens, start=1)]
    )

    payload = await get_tasks_scale(range="30d", quantile=0.95)

    assert payload["output_tokens"] == percentile([float(value) for value in tokens], 0.95)


@pytest.mark.asyncio
async def test_tasks_scale_ignores_runs_outside_the_window(empty_store):
    empty_store.insert_tasks([sized_row(1, output_tokens=5000, minutes_ago=60 * 24 * 3)])
    empty_store.insert_tasks([sized_row(2, output_tokens=80, minutes_ago=5)])

    assert (await get_tasks_scale(range="1h", quantile=0.95))["output_tokens"] == 80.0
    assert (await get_tasks_scale(range="30d", quantile=0.95))["output_tokens"] == 5000.0


@pytest.mark.asyncio
async def test_tasks_scale_on_an_empty_window_has_no_ceiling(empty_store):
    payload = await get_tasks_scale(range="30d", quantile=0.95)

    # None rather than 0: a zero ceiling would draw every mark at max radius.
    assert payload["output_tokens"] is None
    assert payload["count"] == 0


@pytest.mark.asyncio
async def test_tasks_series_carries_a_window_summary(empty_store):
    empty_store.insert_tasks([recent_row(10, 10.0), recent_row(5, 20.0)])

    summary = (await get_tasks_series(range="24h"))["summary"]

    assert summary["count"] == 2
    assert summary["gen_tps_mean"] == 15.0
    assert summary["gen_tps_p95"] == 20.0


@pytest.mark.asyncio
async def test_tasks_series_summary_is_empty_not_absent(empty_store):
    payload = await get_tasks_series(range="7d")

    assert payload["summary"]["count"] == 0
    assert payload["summary"]["gen_tps_p95"] == 0.0


# ── Through the real app: query bounds and the access-control middleware ──

API_KEY = "test-key"
KEYED = {"x-lcc-api-key": API_KEY}


@pytest.fixture
def client(empty_store, monkeypatch, tmp_path):
    from starlette.testclient import TestClient

    from app.main import app

    monkeypatch.setattr("app.services.security.AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.setattr("app.config.settings.require_auth", True)
    monkeypatch.setattr("app.config.settings.lcc_api_key", API_KEY)
    # Not entered as a context manager: the lifespan would start the samplers.
    return TestClient(app, base_url="http://127.0.0.1:17600", client=("127.0.0.1", 50000))


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/metrics/tasks"), ("GET", "/api/metrics/tasks/csv"),
     ("POST", "/api/metrics/clear?scope=buffer")],
)
def test_task_routes_need_the_key(client, method, path):
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, headers=KEYED).status_code == 200


@pytest.mark.parametrize(("n", "status"), [(0, 422), (1, 200), (5000, 200), (5001, 422)])
def test_tasks_route_bounds_n(client, n, status):
    assert client.get(f"/api/metrics/tasks?n={n}", headers=KEYED).status_code == status


def test_tasks_route_answers_400_to_a_bad_bound(client):
    response = client.get("/api/metrics/tasks?since=yesterday", headers=KEYED)

    assert response.status_code == 400
    assert "since" in response.json()["detail"]


def test_tasks_csv_route_streams_a_header_and_rejects_an_unknown_range(client, empty_store):
    empty_store.insert_tasks([recent_row(5, 13.84)])

    response = client.get("/api/metrics/tasks/csv?range=24h", headers=KEYED)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.splitlines()[0].startswith("timestamp,model,")
    assert len(response.text.splitlines()) == 2
    assert client.get("/api/metrics/tasks/csv?range=2d", headers=KEYED).status_code == 400


def test_clear_route_needs_a_scope(client):
    assert client.post("/api/metrics/clear", headers=KEYED).status_code == 400
    assert client.post("/api/metrics/clear?scope=all", headers=KEYED).status_code == 400
    assert client.post("/api/metrics/clear?scope=buffer", headers=KEYED).json() == {
        "cleared": True, "scope": "buffer"
    }


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/metrics/tasks/series"), ("GET", "/api/metrics/tasks/scale"),
     ("GET", "/api/metrics/hardware/series"), ("GET", "/api/metrics/history/summary"),
     ("POST", "/api/metrics/clear?scope=history")],
)
def test_history_routes_need_the_key(client, method, path):
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, headers=KEYED).status_code == 200


@pytest.mark.parametrize(
    "path", ["/api/metrics/tasks/series", "/api/metrics/hardware/series",
             "/api/metrics/tasks/scale"],
)
def test_series_routes_reject_an_unknown_range(client, path):
    assert client.get(f"{path}?range=2d", headers=KEYED).status_code == 400


@pytest.mark.parametrize(("quantile", "status"), [(0, 422), (0.5, 200), (1, 200), (1.5, 422)])
def test_tasks_scale_route_bounds_the_quantile(client, quantile, status):
    path = f"/api/metrics/tasks/scale?quantile={quantile}"

    assert client.get(path, headers=KEYED).status_code == status


def test_tasks_route_returns_20_records_by_default(client, empty_store):
    empty_store.insert_tasks([sized_row(index, 61) for index in range(25)])

    assert len(client.get("/api/metrics/tasks", headers=KEYED).json()["tasks"]) == 20
