from app.models.schemas import LastTaskStats
from app.services.metrics import task_history
from app.services.metrics.task_history import TaskHistory


def _history(monkeypatch, tmp_path, tasks: list[LastTaskStats]) -> TaskHistory:
    monkeypatch.setattr(task_history, "HISTORY_FILE", tmp_path / "task_history.json")
    monkeypatch.setattr(task_history.capabilities, "cmd_journalctl", True)
    queue = iter(tasks)
    monkeypatch.setattr(task_history, "parse_last_task", lambda: next(queue))
    return TaskHistory()


def _task(completed_at: str | None, model: str | None = "Qwen3.5-9B-GGUF") -> LastTaskStats:
    return LastTaskStats(
        available=True,
        model=model,
        completed_at=completed_at,
        input_tokens=4,
        output_tokens=7,
        generation_tps=32.28,
        total_duration_seconds=0.3,
    )


def test_task_history_records_model_and_log_time(monkeypatch, tmp_path):
    history = _history(monkeypatch, tmp_path, [_task("2026-11-08T08:48:05.029000+00:00")])

    history.refresh_from_logs()

    [record] = history._tasks
    assert record.model == "Qwen3.5-9B-GGUF"
    assert record.timestamp == "2026-11-08T08:48:05.029000+00:00"
    assert record.finish_confidence == "unknown"


def test_task_history_keeps_identical_requests_with_different_log_times(monkeypatch, tmp_path):
    history = _history(monkeypatch, tmp_path, [
        _task("2026-11-08T08:44:50.940000+00:00"),
        _task("2026-11-08T08:44:50.940000+00:00"),
        _task("2026-11-08T08:44:51.187000+00:00"),
    ])

    for _ in range(3):
        history.refresh_from_logs()

    assert len(history._tasks) == 2


def test_task_history_marks_model_unknown_for_legacy_logs(monkeypatch, tmp_path):
    history = _history(monkeypatch, tmp_path, [_task(None, model=None)])

    history.refresh_from_logs()

    assert history._tasks[0].model == "unknown"
