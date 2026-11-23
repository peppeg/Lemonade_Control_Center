import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.models.schemas import LogEntryLevel
from app.services.log_parser import (
    _parse_log_line,
    extract_task_records,
    get_logs_for_window,
    parse_last_task,
    parse_task_records,
)


def test_backend_install_line_is_backend_event():
    entry = _parse_log_line(
        "2026-07-09 16:57:15.094 [Info] (Server) "
        "Installing backend: llamacpp:vulkan"
    )

    assert entry.level == LogEntryLevel.BACKEND


def test_llama_server_upgrade_line_is_update_event():
    entry = _parse_log_line(
        "2026-07-09 16:57:15.395 [Info] (llamacpp Server) "
        "Upgrading llama-server from b9585 to b9747"
    )

    assert entry.level == LogEntryLevel.UPDATE


def test_model_update_line_is_update_event():
    entry = _parse_log_line(
        "2026-07-09 06:21:31.980 [Info] (ModelManager) "
        "Update available for unsloth/Qwen3.6-27B-MTP-GGUF: "
        "cached=b3a58239d8d4, latest=5cb35eb3dcbf (1 variant(s))"
    )

    assert entry.level == LogEntryLevel.UPDATE


def test_expected_nvidia_detection_error_on_amd_is_warning():
    entry = _parse_log_line(
        "2026-07-09 06:21:31.185 [Info] (ModelManager) "
        "- NVIDIA GPU: detection error: No NVIDIA discrete GPU found"
    )

    assert entry.level == LogEntryLevel.WARNING


def test_warning_marker_with_error_text_is_warning():
    entry = _parse_log_line(
        "[2026/07/09 06:21:30:9138] W: [null wsi]: "
        "lws_socket_bind: setsockopt bind to device 127.0.0.1 error fd 3 (19)"
    )

    assert entry.level == LogEntryLevel.WARNING


def test_get_logs_for_window_uses_journal_timestamp_and_parses_messages(monkeypatch):
    journal_rows = [
        {
            "__REALTIME_TIMESTAMP": "1783695600123456",
            "MESSAGE": "eval time = 100.0 ms / 4 tokens (40.0 tokens per second)",
        },
        {
            "__REALTIME_TIMESTAMP": "1783695601123456",
            "MESSAGE": "slot released",
        },
    ]
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout="\n".join(json.dumps(row) for row in journal_rows),
        )

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)
    started_at = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    ended_at = datetime(2026, 7, 10, 12, 1, tzinfo=UTC)

    response = get_logs_for_window(started_at, ended_at, max_lines=1)

    assert response.source == "journalctl"
    assert response.total_lines == 1
    assert response.entries[0].level == LogEntryLevel.SLOT
    assert response.entries[0].timestamp == "2026-07-10T15:00:01.123456+00:00"
    assert observed["command"] == [
        "journalctl",
        "-u",
        "lemond.service",
        "--since",
        "2026-07-10T12:00:00+00:00",
        "--until",
        "2026-07-10T12:01:00+00:00",
        "-n",
        "1",
        "-o",
        "json",
        "--no-pager",
    ]


def test_get_logs_for_window_reports_unavailable_on_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="journalctl", timeout=3)

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)
    now = datetime.now(UTC)

    response = get_logs_for_window(now, now)

    assert response.source == "unavailable"
    assert response.entries == []


def _fake_journal(monkeypatch, lines):
    """Make parse_last_task see exactly these journal lines."""
    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="\n".join(lines))

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)


def test_parse_last_task_reads_single_line_telemetry(monkeypatch):
    _fake_journal(monkeypatch, [
        "2026-08-22 10:11:10.139 [Info] (Server) POST /api/v1/chat/completions - 200 OK",
        (
            "2026-08-22 10:11:15.874 [Info] (Telemetry) Inference completed: "
            "model=Gemma-4-12B-it-MTP-GGUF, tokens=152 (in=91, out=61), "
            "ttft=1.24s, tps=13.84"
        ),
    ])

    stats = parse_last_task()

    assert stats.available is True
    assert stats.input_tokens == 91
    assert stats.output_tokens == 61
    assert stats.ttft_seconds == 1.24
    assert stats.generation_tps == 13.84
    assert stats.model == "Gemma-4-12B-it-MTP-GGUF"
    assert stats.completed_at == datetime(2026, 8, 22, 10, 11, 15, 874000).astimezone(UTC).isoformat()


def test_parse_last_task_still_reads_legacy_per_field_telemetry(monkeypatch):
    _fake_journal(monkeypatch, [
        "Input tokens: 40",
        "Output tokens: 12",
        "TTFT (s): 0.55",
        "TPS: 22.5",
    ])

    stats = parse_last_task()

    assert stats.input_tokens == 40
    assert stats.output_tokens == 12
    assert stats.ttft_seconds == 0.55
    assert stats.generation_tps == 22.5
    assert stats.model is None
    assert stats.completed_at is None


def test_parse_last_task_derives_rate_and_duration_when_absent(monkeypatch):
    """The single-line format reports neither, so both are reconstructed."""
    _fake_journal(monkeypatch, [
        (
            "2026-08-22 10:11:15.874 [Info] (Telemetry) Inference completed: "
            "model=Gemma-4-12B-it-MTP-GGUF, tokens=152 (in=91, out=61), "
            "ttft=1.24s, tps=13.84"
        ),
    ])

    stats = parse_last_task()

    assert stats.prompt_eval_tps == 73.39          # 91 / 1.24
    assert stats.total_duration_seconds == 5.6     # 1.24 + 61 / 13.84


def test_parse_last_task_prefers_measured_over_derived(monkeypatch):
    """llama.cpp timings win whenever the log still carries them."""
    _fake_journal(monkeypatch, [
        (
            "prompt eval time = 455.00 ms / 91 tokens "
            "(5.00 ms per token, 200.00 tokens per second)"
        ),
        "total time = 9000.00 ms / 152 tokens",
        (
            "2026-08-22 10:11:15.874 [Info] (Telemetry) Inference completed: "
            "model=Gemma-4-12B-it-MTP-GGUF, tokens=152 (in=91, out=61), "
            "ttft=1.24s, tps=13.84"
        ),
    ])

    stats = parse_last_task()

    assert stats.prompt_eval_tps == 200.0
    assert stats.total_duration_seconds == 9.0


def test_parse_last_task_unavailable_without_journal(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("journalctl")

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)

    assert parse_last_task().available is False


# ── Multi-record extraction ────────────────────────────────

FIXTURE = Path(__file__).parent / "fixtures" / "lemond_journal_11_7.log"


def _fixture_lines() -> list[str]:
    return FIXTURE.read_text(encoding="utf-8").splitlines()


def test_extract_task_records_finds_every_record_in_a_real_journal():
    """The captured 11.7 slice holds nine completed inferences."""
    records = extract_task_records(_fixture_lines())

    assert len(records) == 9
    assert [record.output_tokens for record in records] == [
        38, 79, 562, 10, 217, 61, 24, 55, 61
    ]
    assert [record.input_tokens for record in records] == [
        27, 21, 26, 2306, 24124, 2337, 91, 49, 91
    ]
    assert {record.model for record in records} == {"Gemma-4-12B-it-MTP-GGUF"}


def test_extract_task_records_matches_parse_last_task_on_the_final_record():
    """The multi-record path derives exactly what parse_last_task derives."""
    last = extract_task_records(_fixture_lines())[-1]

    assert last.input_tokens == 91
    assert last.output_tokens == 61
    assert last.ttft_seconds == 1.24
    assert last.generation_tps == 13.84
    assert last.prompt_eval_tps == 73.39          # 91 / 1.24
    assert last.total_duration_seconds == 5.6     # 1.24 + 61 / 13.84


def test_extract_task_records_ignores_the_surrounding_journal_noise():
    """An image model loading, VRAM pressure warnings and an eviction."""
    noise = [
        line for line in _fixture_lines()
        if "(Telemetry) Inference completed" not in line
    ]

    assert len(noise) == 53
    assert extract_task_records(noise) == []


def test_extract_task_records_reads_timestamps_from_the_journal_lines():
    records = extract_task_records(_fixture_lines())
    stamps = [record.timestamp for record in records]

    assert len(set(stamps)) == 9
    assert stamps == sorted(stamps)
    assert all(stamp.endswith("+00:00") for stamp in stamps)


def test_extract_task_records_splits_consecutive_legacy_records():
    """The per-field spelling separates records when a field repeats."""
    records = extract_task_records([
        "Input tokens: 40",
        "Output tokens: 12",
        "TTFT (s): 0.55",
        "TPS: 22.5",
        "Input tokens: 80",
        "Output tokens: 24",
        "TTFT (s): 1.10",
        "TPS: 20.0",
    ])

    assert len(records) == 2
    assert [record.input_tokens for record in records] == [40, 80]
    assert [record.output_tokens for record in records] == [12, 24]
    assert [record.generation_tps for record in records] == [22.5, 20.0]
    assert records[0].model == "unknown"


def test_extract_task_records_drops_records_without_output_tokens():
    """A request that produced nothing is not a data point."""
    assert extract_task_records([
        ("2026-08-22 10:11:15.874 [Info] (Telemetry) Inference completed: "
        "model=X, tokens=91 (in=91, out=0), ttft=1.24s, tps=0.00"),
    ]) == []


def test_parse_task_records_reads_the_journal_window(monkeypatch):
    _fake_journal(monkeypatch, _fixture_lines())

    assert len(parse_task_records()) == 9


def test_parse_task_records_returns_empty_without_journal(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("journalctl")

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)

    assert parse_task_records() == []


def test_parse_task_records_returns_empty_on_a_quiet_journal(monkeypatch):
    _fake_journal(monkeypatch, [])

    assert parse_task_records() == []
