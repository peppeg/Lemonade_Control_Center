import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.schemas import LogEntryLevel
from app.services.log_parser import (
    JournalReadError,
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
    assert all(record.dated for record in records)


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
    # No line carried a timestamp, so the stored time is only the read time.
    assert not any(record.dated for record in records)


# Three legacy records, one field per line, as older Lemonade logged them.
LEGACY_RECORDS = [(40, 12, 22.5), (80, 24, 20.0), (120, 36, 18.0)]
LEGACY_WINDOW = [
    line
    for input_tokens, output_tokens, tps in LEGACY_RECORDS
    for line in (
        f"Input tokens: {input_tokens}",
        f"Output tokens: {output_tokens}",
        "TTFT (s): 0.50",
        f"TPS: {tps}",
    )
]


def _identities(records):
    return [(r.input_tokens, r.output_tokens, r.generation_tps) for r in records]


def test_a_window_starting_inside_a_legacy_record_does_not_shift_later_ones():
    """Reported in review: the window started at an Output tokens line."""
    for dropped in (1, 2, 3):
        records = extract_task_records(LEGACY_WINDOW[dropped:])

        assert _identities(records) == LEGACY_RECORDS[1:], f"first {dropped} lines dropped"


def test_a_legacy_record_still_being_written_is_left_for_the_next_read():
    for kept in (1, 2, 3):
        window = LEGACY_WINDOW[: 8 + kept]

        assert _identities(extract_task_records(window)) == LEGACY_RECORDS[:2], f"{kept} lines"

    assert _identities(extract_task_records(LEGACY_WINDOW)) == LEGACY_RECORDS


def test_every_window_yields_only_true_legacy_records():
    """Wherever the window starts and ends, no record is invented."""
    for start in range(len(LEGACY_WINDOW)):
        for end in range(start, len(LEGACY_WINDOW) + 1):
            found = _identities(extract_task_records(LEGACY_WINDOW[start:end]))
            whole = [
                record
                for index, record in enumerate(LEGACY_RECORDS)
                if start <= 4 * index and 4 * index + 4 <= end
            ]

            assert found == whole, (start, end)


def test_a_legacy_record_missing_its_input_line_does_not_borrow_one():
    """A record whose start was lost mid-journal is dropped, not merged."""
    window = LEGACY_WINDOW[:4] + LEGACY_WINDOW[5:]

    assert _identities(extract_task_records(window)) == [LEGACY_RECORDS[0], LEGACY_RECORDS[2]]


def test_a_legacy_record_with_a_lost_line_does_not_borrow_from_the_next():
    """The next record lost its input line: its TTFT is not the first one's."""
    window = ["Input tokens: 40", "Output tokens: 12", "TPS: 22.5", "Output tokens: 24", "TTFT (s): 1.10", "TPS: 20.0"]

    records = extract_task_records(window)

    assert _identities(records) == [(40, 12, 22.5)]
    assert records[0].ttft_seconds == 0.0


def test_the_last_task_does_not_borrow_from_a_record_that_lost_its_input_line(monkeypatch):
    _fake_journal(monkeypatch, ["Input tokens: 40", "Output tokens: 12", "Output tokens: 24", "TTFT (s): 1.10", "TPS: 20.0"])

    stats = parse_last_task()

    assert (stats.input_tokens, stats.output_tokens, stats.ttft_seconds, stats.generation_tps) == (40, 12, None, None)


def test_a_repeated_field_keeps_its_first_value_as_in_the_last_task():
    """Stored records are split like the last task (#52)."""
    records = extract_task_records(["Input tokens: 80", "Output tokens: 24", "out=9, tps=12.0", "TTFT (s): 0.50"])

    assert _identities(records) == [(80, 24, 12.0)]


def test_a_record_is_not_dated_by_an_earlier_unrelated_line():
    """Otherwise its time would change when that line leaves the window."""
    records = extract_task_records([
        "2026-08-22 10:11:10.139 [Info] (Server) POST /api/v1/chat/completions - 200 OK",
        *LEGACY_WINDOW[:4],
    ])

    assert [record.dated for record in records] == [False]


# Lemonade 2026.45.3, from review: lines from two threads interleave, the
# (Telemetry) and (Process) tags are swapped, and the "total time" line of the
# second task is missing. The first task is a longer one whose total time a
# parser could wrongly carry over.
LEMONADE_2026_45_3 = [
    "2026-11-23 16:07:18.410 [Info] (Process) 0.18.420.105 I slot print_timing: id  0 | task 0 | prompt eval time =     902.11 ms /    50 tokens (   18.04 ms per token,    55.43 tokens per second)",
    "2026-11-23 16:07:29.910 [Info] (Process) 0.18.420.106 I slot print_timing: id  0 | task 0 |        eval time =   10597.80 ms /   300 tokens (   35.33 ms per token,    28.31 tokens per second)",
    "2026-11-23 16:07:29.910 [Info] (Process) 0.18.420.107 I slot print_timing: id  0 | task 0 |       total time =   11499.91 ms /   350 tokens",
    "2026-11-23 16:07:29.911 [Info] (Telemetry) Inference completed: model=Gemma-4-31B-it-MTP-GGUF, tokens=350 (in=50, out=300), ttft=0.902s, tps=28.31",
    "2026-11-23 16:07:41.036 [Info] (Process) 0.18.432.412 I slot print_timing: id  0 | task 0 | prompt eval time =     484.83 ms /    27 tokens (   17.96 ms per token,    55.69 tokens per second)",
    "2026-11-23 16:07:41.037 [Info] (Telemetry) 0.18.432.417 I slot print_timing: id  0 | task 0 |        eval time =    4699.53 ms /   134 tokens (   35.33 ms per token,    28.30 tokens per second)",
    "2026-11-23 16:07:41.037 [Info] (Process) Inference completed: model=Gemma-4-31B-it-MTP-GGUF, tokens=161 (in=27, out=134), ttft=0.485s, tps=28.30",
]


def test_interleaved_lemonade_2026_45_3_lines_give_each_task_its_own_numbers(monkeypatch):
    _fake_json_journal(monkeypatch, LEMONADE_2026_45_3)

    first, second = parse_task_records()

    assert (second.input_tokens, second.output_tokens) == (27, 134)
    assert second.model == "Gemma-4-31B-it-MTP-GGUF"
    assert second.ttft_seconds == pytest.approx(0.485)
    assert second.generation_tps == pytest.approx(28.30)
    assert second.prompt_eval_tps == pytest.approx(55.67)   # 27 / 0.485
    # 0.485 + 134 / 28.30 = 5.2s, not the 11.5s of the task before it.
    assert second.total_duration_seconds == pytest.approx(5.2)
    assert first.total_duration_seconds == pytest.approx(11.5)
    assert second.timestamp == extract_task_records(LEMONADE_2026_45_3[-1:])[0].timestamp
    assert second.dated


def test_a_telemetry_tagged_timing_line_is_not_a_record_of_its_own():
    assert extract_task_records(LEMONADE_2026_45_3[4:6]) == []


def test_extract_task_records_drops_records_without_output_tokens():
    """A request that produced nothing is not a data point."""
    assert extract_task_records([
        ("2026-08-22 10:11:15.874 [Info] (Telemetry) Inference completed: "
        "model=X, tokens=91 (in=91, out=0), ttft=1.24s, tps=0.00"),
    ]) == []


def _fake_json_journal(monkeypatch, lines, start_us=1_787_400_000_000_000):
    """Make parse_task_records see these lines, received one second apart."""
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        entries = [
            {"MESSAGE": line, "__REALTIME_TIMESTAMP": str(start_us + index * 1_000_000)}
            for index, line in enumerate(lines)
        ]
        return SimpleNamespace(
            returncode=0, stdout="\n".join(json.dumps(entry) for entry in entries), stderr=""
        )

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)
    return commands


def _received(start_us: int, index: int) -> str:
    return datetime.fromtimestamp(start_us / 1_000_000 + index, tz=UTC).isoformat()


def test_parse_task_records_reads_the_journal_window(monkeypatch):
    commands = _fake_json_journal(monkeypatch, _fixture_lines())

    records = parse_task_records()

    assert len(records) == 9
    assert "json" in commands[0]
    # Lemonade's own timestamp wins over the time journald received the line,
    # so records keep the time main and the JSON history recorded for them.
    assert [record.timestamp for record in records] == [
        record.timestamp for record in extract_task_records(_fixture_lines())
    ]


def test_parse_task_records_dates_legacy_records_by_their_journal_entry(monkeypatch):
    start_us = 1_787_400_000_000_000
    _fake_json_journal(monkeypatch, LEGACY_WINDOW, start_us)

    records = parse_task_records()

    assert all(record.dated for record in records)
    # Each record is dated by its Input tokens line, the 1st, 5th and 9th.
    assert [record.timestamp for record in records] == [
        _received(start_us, index) for index in (0, 4, 8)
    ]


def test_legacy_record_dates_do_not_depend_on_the_window(monkeypatch):
    start_us = 1_787_400_000_000_000
    _fake_json_journal(monkeypatch, LEGACY_WINDOW, start_us)
    whole = parse_task_records()

    _fake_json_journal(monkeypatch, LEGACY_WINDOW[2:], start_us + 2_000_000)
    moved = parse_task_records()

    assert [record.timestamp for record in moved] == [record.timestamp for record in whole[1:]]


def test_parse_task_records_reads_messages_journald_stored_as_bytes(monkeypatch):
    line = _fixture_lines()[-1]
    entry = {"MESSAGE": list(line.encode()), "__REALTIME_TIMESTAMP": "1787400000000000"}
    monkeypatch.setattr(
        "app.services.log_parser.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(entry), stderr=""
        ),
    )

    [record] = parse_task_records()

    assert record.input_tokens == 91


def test_parse_task_records_reports_a_missing_journalctl(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("journalctl")

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)

    with pytest.raises(JournalReadError, match="could not be run"):
        parse_task_records()


def test_parse_task_records_reports_a_journal_it_may_not_read(monkeypatch):
    """journalctl --system fails, rather than showing nothing, without access."""
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="No journal files were opened due to insufficient permissions.\n",
        )

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)

    with pytest.raises(JournalReadError, match="insufficient permissions"):
        parse_task_records()
    assert "--system" in commands[0]


def test_parse_task_records_reports_a_journalctl_timeout(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))

    monkeypatch.setattr("app.services.log_parser.subprocess.run", fake_run)

    with pytest.raises(JournalReadError):
        parse_task_records()


def test_parse_task_records_reports_output_it_cannot_read(monkeypatch):
    monkeypatch.setattr(
        "app.services.log_parser.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=0, stdout="journalctl: unrecognized option\n", stderr=""
        ),
    )

    with pytest.raises(JournalReadError):
        parse_task_records()


def test_parse_task_records_returns_empty_on_a_quiet_journal(monkeypatch):
    _fake_json_journal(monkeypatch, [])

    assert parse_task_records() == []
