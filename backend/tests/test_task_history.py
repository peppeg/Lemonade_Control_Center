import json
from datetime import UTC, datetime, timedelta

from app.services.log_parser import extract_task_records
from app.services.metrics import task_history
from app.services.metrics.store import MetricsStore
from app.services.metrics.task_history import TaskHistory


def _history(monkeypatch, tmp_path, journals: list[list[str]]) -> TaskHistory:
    monkeypatch.setattr(task_history.capabilities, "cmd_journalctl", True)
    queue = iter(journals)
    monkeypatch.setattr(
        task_history, "parse_task_records", lambda **_: extract_task_records(next(queue))
    )
    return TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))


def _line(stamp: str, model: str = "Qwen3.5-9B-GGUF") -> str:
    return (
        f"{stamp} [Info] (Telemetry) Inference completed: "
        f"model={model}, tokens=11 (in=4, out=7), ttft=0.08s, tps=32.28"
    )


def _legacy() -> list[str]:
    return ["Input tokens: 4", "Output tokens: 7", "TTFT (s): 0.08", "TPS: 32.28"]


def test_task_history_records_model_and_log_time(monkeypatch, tmp_path):
    history = _history(monkeypatch, tmp_path, [[_line("2026-11-08 08:48:05.029")]])

    history.refresh_from_logs()

    [record] = history.get_recent(refresh=False)
    assert record["model"] == "Qwen3.5-9B-GGUF"
    assert record["timestamp"] == extract_task_records([_line("2026-11-08 08:48:05.029")])[0].timestamp
    # The enum value, not str(enum): "inferred", never "FinishReasonConfidence.INFERRED".
    assert record["finish_confidence"] == "inferred"


def test_task_history_keeps_identical_requests_with_different_log_times(monkeypatch, tmp_path):
    history = _history(monkeypatch, tmp_path, [
        [_line("2026-11-08 08:44:50.940")],
        [_line("2026-11-08 08:44:50.940")],
        [_line("2026-11-08 08:44:51.187")],
    ])

    for _ in range(3):
        history.refresh_from_logs()

    assert history.count() == 2


def test_task_history_marks_model_unknown_for_legacy_logs(monkeypatch, tmp_path):
    history = _history(monkeypatch, tmp_path, [_legacy()])

    history.refresh_from_logs()

    assert history.get_recent(refresh=False)[0]["model"] == "unknown"


def test_task_history_drops_the_single_token_sentinel_rate(monkeypatch, tmp_path):
    """Lemonade logs tps=1000000.00 for a one-token completion."""
    line = (
        "2026-11-08 08:48:05.029 [Info] (Telemetry) Inference completed: "
        "model=Qwen3.5-9B-GGUF, tokens=15894 (in=15893, out=1), ttft=17.60s, tps=1000000.00"
    )
    history = _history(monkeypatch, tmp_path, [[line]])

    history.refresh_from_logs()

    [record] = history.get_recent(refresh=False)
    assert record["output_tokens"] == 1
    assert record["gen_tps"] == 0.0
    assert history.store.task_window(
        datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 30, tzinfo=UTC), 3600
    )["summary"]["gen_tps_mean"] == 0.0


def test_task_history_stores_an_undated_record_once(monkeypatch, tmp_path):
    """A legacy record without a log timestamp is matched on its metrics alone.

    Its timestamp is the time it was read, so it differs on every sampler tick;
    without the fallback each tick would insert the same record again.
    """
    history = _history(monkeypatch, tmp_path, [_legacy(), _legacy()])

    history.refresh_from_logs()
    history.refresh_from_logs()

    assert history.count() == 1


def test_undated_record_is_skipped_when_its_metrics_are_already_stored(monkeypatch, tmp_path):
    history = _history(monkeypatch, tmp_path, [[_line("2026-11-08 08:48:05.029")], _legacy()])

    history.refresh_from_logs()
    history.refresh_from_logs()

    assert history.count() == 1


def test_undated_records_with_different_metrics_are_both_stored(monkeypatch, tmp_path):
    other = ["Input tokens: 5", "Output tokens: 9", "TTFT (s): 0.10", "TPS: 30.00"]
    history = _history(monkeypatch, tmp_path, [_legacy(), other])

    history.refresh_from_logs()
    history.refresh_from_logs()

    assert history.count() == 2


def test_a_moving_window_over_legacy_records_stores_each_record_once(monkeypatch, tmp_path):
    records = [
        line
        for input_tokens, output_tokens in ((40, 12), (80, 24), (120, 36))
        for line in (
            f"Input tokens: {input_tokens}",
            f"Output tokens: {output_tokens}",
            "TTFT (s): 0.50",
            f"TPS: {output_tokens / 2}",
        )
    ]
    windows = [records[dropped:] for dropped in (3, 2, 1, 0)] + [records[:10], records]
    history = _history(monkeypatch, tmp_path, windows)

    for _ in windows:
        history.refresh_from_logs()

    stored = history.get_recent(refresh=False)
    assert sorted((row["input_tokens"], row["output_tokens"]) for row in stored) == [
        (40, 12), (80, 24), (120, 36)
    ]


def test_cleared_history_does_not_come_back_from_the_journal(monkeypatch, tmp_path):
    """Reported in review: a cleared task reappeared on the next read."""
    journal = [_line("2026-11-08 08:44:50.940"), _line("2026-11-08 08:44:51.187")]
    later = [*journal, _line("2026-11-08 08:46:00.000")]
    history = _history(monkeypatch, tmp_path, [journal, journal, later])
    history.refresh_from_logs()
    [_, last] = extract_task_records(journal)
    cleared_at = datetime.fromisoformat(last.timestamp) + timedelta(seconds=30)

    assert history.clear(now=cleared_at) == {"tasks": 2, "hardware": 0}

    assert history.refresh_from_logs() == 0
    assert history.count() == 0
    # A genuinely new task after the clear is still recorded.
    assert history.refresh_from_logs() == 1
    assert [row["timestamp"] for row in history.get_recent(refresh=False)] == [
        extract_task_records(later)[-1].timestamp
    ]


def test_cleared_legacy_records_do_not_come_back_either(monkeypatch, tmp_path):
    """Dated by journald, legacy records fall on one side of the cut-off."""
    monkeypatch.setattr(task_history.capabilities, "cmd_journalctl", True)
    received = datetime(2026, 11, 8, 8, 44, tzinfo=UTC)
    lines = _legacy() + ["Input tokens: 5", "Output tokens: 9", "TTFT (s): 0.10", "TPS: 30.00"]
    times = [(received + timedelta(seconds=index)).isoformat() for index in range(len(lines))]
    windows = iter([4, 4, 8])
    monkeypatch.setattr(
        task_history,
        "parse_task_records",
        lambda **_: extract_task_records(lines[: (end := next(windows))], times[:end]),
    )
    history = TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))
    history.refresh_from_logs()

    history.clear(now=received + timedelta(seconds=2))

    assert history.refresh_from_logs() == 0
    assert history.refresh_from_logs() == 1
    assert [row["input_tokens"] for row in history.get_recent(refresh=False)] == [5]


def test_a_legacy_record_imported_from_the_json_history_is_not_stored_twice(
    monkeypatch, tmp_path
):
    """The JSON history dated legacy records by when they were polled."""
    received = datetime(2026, 11, 8, 8, 44, tzinfo=UTC)
    times = [(received + timedelta(milliseconds=index)).isoformat() for index in range(8)]
    lines = _legacy() + _legacy()
    history = _history(monkeypatch, tmp_path, [])
    monkeypatch.setattr(
        task_history,
        "parse_task_records",
        lambda **_: extract_task_records(lines[:4], times[:4]),
    )
    legacy = tmp_path / "task_history.json"
    legacy.write_text(json.dumps({"tasks": [{
        "timestamp": (received + timedelta(seconds=7)).isoformat(), "model": "unknown",
        "input_tokens": 4, "output_tokens": 7, "prompt_tps": 50.0, "gen_tps": 32.28,
        "ttft_seconds": 0.08, "total_seconds": 0.3, "finish_reason": "stop",
        "finish_confidence": "inferred",
    }]}), encoding="utf-8")

    assert history.migrate_legacy_json(legacy) == 1
    assert history.refresh_from_logs() == 0
    assert history.count() == 1


def test_identical_legacy_runs_at_different_times_are_two_rows(monkeypatch, tmp_path):
    received = datetime(2026, 11, 8, 8, 44, tzinfo=UTC)
    lines = _legacy() + _legacy()
    times = [(received + timedelta(seconds=index)).isoformat() for index in range(8)]
    history = _history(monkeypatch, tmp_path, [])
    windows = iter([4, 8, 8])
    monkeypatch.setattr(
        task_history,
        "parse_task_records",
        lambda **_: extract_task_records(lines[: (end := next(windows))], times[:end]),
    )

    for _ in range(3):
        history.refresh_from_logs()

    assert history.count() == 2


def _legacy_json(path, received: datetime, count: int = 1, step=timedelta(seconds=7)):
    path.write_text(json.dumps({"tasks": [{
        "timestamp": (received + step * (index + 1)).isoformat(), "model": "unknown",
        "input_tokens": 4, "output_tokens": 7, "prompt_tps": 50.0, "gen_tps": 32.28,
        "ttft_seconds": 0.08, "total_seconds": 0.3, "finish_reason": "stop",
        "finish_confidence": "inferred",
    } for index in range(count)]}), encoding="utf-8")
    return path


def test_a_legacy_record_read_before_the_json_import_is_not_stored_twice(tmp_path):
    """Reported in review: the import failed once, or a read came first."""
    received = datetime(2026, 11, 8, 8, 44, tzinfo=UTC)
    times = [(received + timedelta(milliseconds=index)).isoformat() for index in range(4)]
    history = TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))

    assert history.ingest(extract_task_records(_legacy(), times)) == 1
    assert history.migrate_legacy_json(_legacy_json(tmp_path / "task_history.json", received)) == 0
    assert history.count() == 1


def test_repeated_runs_in_the_json_history_are_all_imported(tmp_path):
    received = datetime(2026, 11, 8, 8, 44, tzinfo=UTC)
    history = TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))

    assert history.migrate_legacy_json(
        _legacy_json(tmp_path / "task_history.json", received, count=3)
    ) == 3


def test_an_imported_run_later_than_a_stored_one_is_kept(tmp_path):
    """Only a stored run at or before the polled time can be the same run."""
    received = datetime(2026, 11, 8, 8, 44, tzinfo=UTC)
    later = received + timedelta(minutes=10)
    times = [(later + timedelta(milliseconds=index)).isoformat() for index in range(4)]
    history = TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))

    history.ingest(extract_task_records(_legacy(), times))

    assert history.migrate_legacy_json(_legacy_json(tmp_path / "task_history.json", received)) == 1
    assert history.count() == 2


def _legacy_runs(starts: list[datetime], output_tokens: int, tps: float) -> list:
    """Legacy per-field records, one per start, each line received 1 ms apart."""
    lines: list[str] = []
    times: list[str] = []
    for start in starts:
        lines += ["Input tokens: 4", f"Output tokens: {output_tokens}", "TTFT (s): 0.08", f"TPS: {tps}"]
        times += [(start + timedelta(milliseconds=index)).isoformat() for index in range(4)]
    return extract_task_records(lines, times)


def _polled_json(path, polled: datetime, output_tokens: int, tps: float):
    path.write_text(json.dumps({"tasks": [{
        "timestamp": polled.isoformat(), "model": "unknown",
        "input_tokens": 4, "output_tokens": output_tokens, "prompt_tps": 50.0,
        "gen_tps": tps, "ttft_seconds": 0.08, "total_seconds": 0.3,
        "finish_reason": "stop", "finish_confidence": "inferred",
    }]}), encoding="utf-8")
    return path


def test_an_earlier_identical_legacy_run_is_kept_after_the_import(tmp_path):
    """Reported in review: run A at 12:00 is only in the journal; an identical
    run C at 13:00 is in the journal and in the JSON history, polled at
    13:00:30. A once matched C's imported copy and was dropped."""
    first = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    second = first + timedelta(hours=1)
    history = TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))

    assert history.migrate_legacy_json(
        _polled_json(tmp_path / "task_history.json", second + timedelta(seconds=30), 1, 0.0)
    ) == 1
    assert history.ingest(_legacy_runs([first, second], 1, 0.0)) == 1
    assert [row["timestamp"] for row in history.get_recent(refresh=False)] == [
        first.isoformat(),
        (second + timedelta(seconds=30)).isoformat(),
    ]


def test_identical_legacy_runs_a_day_apart_are_kept_after_the_import(tmp_path):
    first = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    second = first + timedelta(days=1)
    history = TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))

    history.migrate_legacy_json(
        _polled_json(tmp_path / "task_history.json", second + timedelta(seconds=10), 7, 32.28)
    )
    history.ingest(_legacy_runs([first, second], 7, 32.28))

    assert history.count() == 2


def test_an_imported_run_long_after_a_stored_identical_one_is_kept(tmp_path):
    """The import matches only within the poll window, as the journal does, so
    the order of the import and the journal read does not change the result."""
    first = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    history = TaskHistory(MetricsStore(tmp_path / "lcc_metrics.db"))

    history.ingest(_legacy_runs([first], 1, 0.0))

    assert history.migrate_legacy_json(
        _polled_json(tmp_path / "task_history.json", first + timedelta(hours=1), 1, 0.0)
    ) == 1
    assert history.count() == 2
