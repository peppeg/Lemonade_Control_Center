import json
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.schemas import LogEntryLevel
from app.services.log_parser import _parse_log_line, get_logs_for_window


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
    started_at = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    ended_at = datetime(2026, 7, 10, 12, 1, tzinfo=timezone.utc)

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
    now = datetime.now(timezone.utc)

    response = get_logs_for_window(now, now)

    assert response.source == "unavailable"
    assert response.entries == []
