from datetime import UTC, datetime

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
