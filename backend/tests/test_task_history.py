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
