"""
Log parser for Lemonade/llama-server journalctl output.

Extracts structured information from raw log lines:
- Prompt eval speed (t/s)
- Generation speed (t/s)
- Token counts
- TTFT
- Finish reason (confirmed vs inferred)
- Slot lifecycle events
"""
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.schemas import (
    FinishReason,
    FinishReasonConfidence,
    LastTaskStats,
    LogEntry,
    LogEntryLevel,
    RecentLogsResponse,
)

# ── Regex patterns for llama-server log parsing ────────────

# Only what int() and float() can read. Anything else is a missing value.
COUNT = r"(\d{1,15})(?!\d)"
NUMBER = r"(\d{1,15}(?:\.\d{1,15})?)(?!\.?\d)"

RE_PROMPT_EVAL = re.compile(
    rf"prompt eval time\s*=\s*[\d.]+\s*ms\s*/\s*{COUNT}\s*tokens?\s*"
    rf"\([^)]*,\s*{NUMBER}\s*tokens?(?:/s|\s+per\s+second)\)"
)

RE_GENERATION = re.compile(
    rf"(?:generation|eval) (?:eval )?time\s*=\s*{NUMBER}\s*ms\s*/\s*{COUNT}\s*tokens?\s*"
    rf"\([^)]*,\s*{NUMBER}\s*tokens?(?:/s|\s+per\s+second)\)"
)

RE_TOTAL_TIME = re.compile(
    rf"total time\s*=\s*{NUMBER}\s*ms\s*/\s*{COUNT}\s*tokens?"
)

RE_SLOT_RELEASED = re.compile(r"slot\s+(?:released|freed)", re.IGNORECASE)
RE_SLOT_PROCESSING = re.compile(r"slot\s+(?:is\s+)?processing", re.IGNORECASE)
RE_SLOT_TRUNCATED = re.compile(rf"truncated\s*=\s*{COUNT}", re.IGNORECASE)

RE_TELEMETRY_INPUT = re.compile(
    rf"(?:\bInput tokens:\s*|\bin=){COUNT}", re.IGNORECASE)
RE_TELEMETRY_OUTPUT = re.compile(
    rf"(?:\bOutput tokens:\s*|\bout=){COUNT}", re.IGNORECASE)
RE_TELEMETRY_TTFT = re.compile(
    rf"(?:\bTTFT\s*\(s\):\s*|\bttft=){NUMBER}", re.IGNORECASE)
RE_TELEMETRY_TPS = re.compile(
    rf"(?:\bTPS:\s*|\btps=){NUMBER}", re.IGNORECASE)
RE_TELEMETRY_MODEL = re.compile(
    r"Inference completed:.*?\bmodel=([^,\s]+)", re.IGNORECASE)

RE_SLOT_TASK = re.compile(r"\bid\s+(\d+)\s*\|\s*task\s+(\d+)")

# Present whenever a task ended, even where its numbers cannot be parsed.
RE_TASK_END = re.compile(r"\b(?:inference completed|eval time|total time)\b", re.IGNORECASE)

RE_MODEL_LOADED = re.compile(r"model\s+loaded|all\s+slots\s+are\s+idle", re.IGNORECASE)

RE_ERROR = re.compile(r"\b(?:error|exception|fail|fatal)\b", re.IGNORECASE)
RE_WARNING = re.compile(r"\b(?:warn|warning|timeout|truncat)\b", re.IGNORECASE)
RE_WARNING_MARKER = re.compile(r"(?:\bW:|\bW\s+[\w_]+:)", re.IGNORECASE)
RE_EXPECTED_DETECTION_ERROR = re.compile(
    r"NVIDIA GPU:\s+detection error:\s+No NVIDIA discrete GPU found",
    re.IGNORECASE,
)

RE_BACKEND_EVENT = re.compile(
    r"\b(?:"
    r"Installing backend|"
    r"Using LlamaCpp Backend|"
    r"Backend availability|"
    r"llama-server is ready|"
    r"Started watchdog for llama-server|"
    r"Process started successfully,\s*PID|"
    r"server is listening on http://"
    r")\b",
    re.IGNORECASE,
)
RE_UPDATE_EVENT = re.compile(
    r"\b(?:"
    r"Update available for|"
    r"Updates available for|"
    r"Upgrading llama-server|"
    r"Installing llama-server"
    r")\b",
    re.IGNORECASE,
)

RE_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.]+[+-]\d{2}:\d{2}|\w{3}\s+\d+\s+[\d:]+)")
RE_LEMONADE_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}\s+[\d:.]+)")


def get_recent_logs(
    service: str = "lemond.service",
    n_lines: int = 100,
    timeout: float = 10,
) -> RecentLogsResponse:
    """Get recent log entries from journalctl, parsed into structured format."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", service, "-n", str(n_lines),
             "-o", "cat", "--no-pager"],
            capture_output=True, text=True, timeout=timeout,
        check=False,
        )
        if result.returncode != 0:
            return RecentLogsResponse(entries=[], total_lines=0, source="error")

        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        entries = [_parse_log_line(line) for line in lines]
        return RecentLogsResponse(
            entries=entries, total_lines=len(lines), source="journalctl"
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return RecentLogsResponse(entries=[], total_lines=0, source="unavailable")


def get_logs_for_window(
    started_at: datetime,
    ended_at: datetime,
    service: str = "lemond.service",
    max_lines: int = 200,
    timeout: float = 3,
) -> RecentLogsResponse:
    """Return structured journald entries emitted during one operator action."""
    since = _as_utc(started_at).isoformat()
    until = _as_utc(ended_at).isoformat()
    try:
        result = subprocess.run(
            [
                "journalctl",
                "-u",
                service,
                "--since",
                since,
                "--until",
                until,
                "-n",
                str(max_lines),
                "-o",
                "json",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return RecentLogsResponse(entries=[], total_lines=0, source="unavailable")

    if result.returncode != 0:
        return RecentLogsResponse(entries=[], total_lines=0, source="error")

    entries: list[LogEntry] = []
    for raw_line in result.stdout.splitlines():
        try:
            payload = json.loads(raw_line)
        except (TypeError, ValueError):
            continue
        message = payload.get("MESSAGE")
        if not isinstance(message, str) or not message.strip():
            continue
        entry = _parse_log_line(message)
        journal_timestamp = _journal_timestamp(payload.get("__REALTIME_TIMESTAMP"))
        if journal_timestamp:
            entry.timestamp = journal_timestamp
        entries.append(entry)

    entries = entries[-max_lines:]
    return RecentLogsResponse(entries=entries, total_lines=len(entries), source="journalctl")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _journal_timestamp(value: object) -> str | None:
    try:
        microseconds = int(str(value))
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(microseconds / 1_000_000, tz=UTC).isoformat()


@dataclass
class _TaskTimings:
    """What llama.cpp logged about one task."""

    first_line: int
    prompt_tokens: int | None = None
    prompt_tps: float | None = None
    output_tokens: int | None = None
    generation_tps: float | None = None
    total_seconds: float | None = None
    total_tokens: int | None = None
    truncated: bool | None = None

    def fits(self, record: dict) -> bool:
        """Whether these timings can belong to a telemetry record."""
        tokens_in, tokens_out = record.get("input_tokens"), record.get("output_tokens")
        if self.output_tokens is not None and tokens_out is not None:
            return self.output_tokens == tokens_out
        if self.total_tokens is not None and tokens_out is not None:
            prompt = self.prompt_tokens if self.prompt_tokens is not None else tokens_in
            return prompt is not None and self.total_tokens == prompt + tokens_out
        # The prompt may be partly cached, so fewer tokens than the request had.
        return self.prompt_tokens is not None and tokens_in is not None and self.prompt_tokens <= tokens_in


def _read_last_task(lines: list[str], stats: LastTaskStats) -> None:
    """Fill `stats` from the newest task only, and tell whether there is one.

    Lemonade logs from several threads: lines can be missing, and a few can land
    after the telemetry of their own task. So the llama.cpp lines are grouped by
    task, and used only when their token counts fit the telemetry record.
    """
    record, start, end = _last_telemetry_record(lines)
    tasks = _task_timings(lines, start)
    if record:
        timings = next((task for task in reversed(tasks) if task.first_line < end and task.fits(record)), None)
    else:
        timings = next((task for task in reversed(tasks) if task.output_tokens is not None), None)

    stats.found = bool(record) or timings is not None or any(RE_TASK_END.search(line) for line in lines)
    for field, value in record.items():
        setattr(stats, field, value)
    if timings is None:
        return
    if stats.input_tokens is None:
        stats.input_tokens = timings.prompt_tokens
    if stats.output_tokens is None:
        stats.output_tokens = timings.output_tokens
    if stats.generation_tps is None:
        stats.generation_tps = timings.generation_tps
    stats.prompt_eval_tps = timings.prompt_tps
    stats.total_duration_seconds = timings.total_seconds
    stats.truncated = timings.truncated


def _last_telemetry_record(lines: list[str]) -> tuple[dict, int, int]:
    """The newest telemetry record, and the range of lines that can concern it.

    The range goes from the end of the previous record to the end of this one.
    """
    found = _telemetry_records(lines)
    if not found:
        return {}, 0, 0
    last = found[-1]
    record = dict(last.fields)
    if "ttft_seconds" in record:
        record["ttft_seconds"] = round(record["ttft_seconds"], 2)
    if "model" in record:
        line = next(lines[i] for i in last.lines if RE_TELEMETRY_MODEL.search(lines[i]))
        record["completed_at"] = _lemonade_timestamp_iso(line)
    start = found[-2].end if len(found) > 1 else 0
    return record, start, last.end


@dataclass
class _TelemetryLines:
    """The lines of one telemetry record, and the fields read from them."""

    lines: list[int]
    fields: dict
    # A line with nothing new for the record ended it.
    closed: bool = False

    @property
    def end(self) -> int:
        return self.lines[-1] + 1


def _telemetry_records(lines: list[str]) -> list[_TelemetryLines]:
    """Split journal lines into telemetry records, oldest first.

    A record is one `Inference completed` line, or the older format with one
    field per line (Input tokens, Output tokens, TTFT, TPS). Both begin with
    the input tokens, so an input-token count always starts a new record,
    and a window that starts inside a record cannot shift the fields of
    later ones. Lines before the first input-token count belong to a record
    whose start is not in the window, and are skipped.

    A later line adds the fields the record does not have yet, and the first
    value of each field is kept. A line with nothing new ends the record:
    the lines up to the next input-token count belong to a record whose
    first line is missing, and are skipped, so one record never takes the
    fields of another.
    """
    records: list[_TelemetryLines] = []
    for index, line in enumerate(lines):
        fields: dict = {}
        if m := RE_TELEMETRY_INPUT.search(line):
            fields["input_tokens"] = int(m.group(1))
        if m := RE_TELEMETRY_OUTPUT.search(line):
            fields["output_tokens"] = int(m.group(1))
        if m := RE_TELEMETRY_TTFT.search(line):
            fields["ttft_seconds"] = float(m.group(1))
        if m := RE_TELEMETRY_TPS.search(line):
            fields["generation_tps"] = float(m.group(1))
        if m := RE_TELEMETRY_MODEL.search(line):
            fields["model"] = m.group(1)

        if "input_tokens" in fields:
            records.append(_TelemetryLines(lines=[], fields={}))
        elif not fields or not records or records[-1].closed:
            continue
        elif fields.keys() <= records[-1].fields.keys():
            records[-1].closed = True
            continue
        record = records[-1]
        record.lines.append(index)
        record.fields = fields | record.fields
    return records


def _task_timings(lines: list[str], start: int) -> list[_TaskTimings]:
    """The llama.cpp tasks that logged something from line `start`, in order of their last line."""
    tasks: dict[object, _TaskTimings] = {}
    for index, line in enumerate(lines[start:], start):
        values: dict = {}
        if m := RE_PROMPT_EVAL.search(line):
            values = {"prompt_tokens": int(m.group(1)), "prompt_tps": float(m.group(2))}
        elif m := RE_GENERATION.search(line):
            values = {"output_tokens": int(m.group(2)), "generation_tps": float(m.group(3))}
        elif m := RE_TOTAL_TIME.search(line):
            values = {"total_seconds": round(float(m.group(1)) / 1000, 1), "total_tokens": int(m.group(2))}
        elif m := RE_SLOT_TRUNCATED.search(line):
            values = {"truncated": bool(int(m.group(1)))}
        if not values:
            continue

        m = RE_SLOT_TASK.search(line)
        key = m.groups() if m else None
        task = tasks.pop(key, None)
        # Lines without a task id: a repeated field, or a new prompt, is a new task.
        if key is None and task and ("prompt_tokens" in values or any(getattr(task, f) is not None for f in values)):
            tasks[index] = task
            task = None
        task = task or _TaskTimings(first_line=index)
        for field, value in values.items():
            setattr(task, field, value)
        tasks[key] = task
    return list(tasks.values())


def parse_last_task(
    service: str = "lemond.service",
    n_lines: int = 200,
    configured_max_tokens: int | None = None,
    timeout: float = 10,
) -> LastTaskStats:
    """Parse the most recent completed task from journalctl logs."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", service, "-n", str(n_lines),
             "-o", "cat", "--no-pager"],
            capture_output=True, text=True, timeout=timeout,
        check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return LastTaskStats(available=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return LastTaskStats(available=False)

    lines = result.stdout.strip().split("\n")

    stats = LastTaskStats(available=True, raw_log_lines=lines[-50:])

    _read_last_task(lines, stats)

    if stats.ttft_seconds is None and stats.prompt_eval_tps and stats.input_tokens:
        stats.ttft_seconds = round(stats.input_tokens / stats.prompt_eval_tps, 2)

    # Lemonade 11.7's single-line telemetry carries no prompt-eval rate. Derive it
    # from the numbers it does report - the same relationship the branch above
    # assumes in reverse. ttft includes queueing, so this reads slightly low: it
    # is an estimate, not a measurement.
    if stats.prompt_eval_tps is None and stats.ttft_seconds and stats.input_tokens:
        stats.prompt_eval_tps = round(stats.input_tokens / stats.ttft_seconds, 2)

    # Same story for wall-clock duration: ttft covers everything up to the first
    # token, the rest arrives at the measured generation rate. Estimate, not a
    # measurement - it excludes teardown after the last token.
    if (stats.total_duration_seconds is None and stats.ttft_seconds
            and stats.output_tokens and stats.generation_tps):
        stats.total_duration_seconds = round(
            stats.ttft_seconds + stats.output_tokens / stats.generation_tps, 1)

    stats.finish_reason = infer_finish_reason(stats, configured_max_tokens)

    return stats


def _lemonade_timestamp_iso(line: str) -> str | None:
    """Convert Lemonade's local, zone-less log timestamp to an aware ISO string."""
    m = RE_LEMONADE_TIMESTAMP.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f").astimezone(UTC).isoformat()
    except ValueError:
        return None


def infer_finish_reason(
    stats: LastTaskStats,
    configured_max_tokens: int | None
) -> FinishReason:
    """Determine finish reason with confidence level."""
    if stats.output_tokens is None:
        return FinishReason(
            reason="unknown",
            confidence=FinishReasonConfidence.UNKNOWN,
            evidence="No output token count available in logs."
        )

    if configured_max_tokens and stats.output_tokens >= configured_max_tokens:
        return FinishReason(
            reason="length",
            confidence=FinishReasonConfidence.INFERRED,
            evidence=f"output_tokens ({stats.output_tokens}) >= "
                     f"configured max_tokens ({configured_max_tokens})"
        )

    common_limits = [512, 1000, 1024, 2000, 2048, 4000, 4096,
                     8000, 8192, 16000, 16384, 32000, 32768]
    if stats.output_tokens in common_limits:
        return FinishReason(
            reason="length",
            confidence=FinishReasonConfidence.INFERRED,
            evidence=f"output_tokens ({stats.output_tokens}) matches a common "
                     f"max_tokens boundary."
        )

    return FinishReason(
        reason="stop",
        confidence=FinishReasonConfidence.INFERRED,
        evidence=f"output_tokens ({stats.output_tokens}) does not match any "
                 f"known max_tokens boundary."
    )


def _parse_log_line(line: str) -> LogEntry:
    """Parse a single log line into a structured LogEntry."""
    timestamp = None
    m = RE_TIMESTAMP.match(line)
    if m:
        timestamp = m.group(1)
    else:
        m = RE_LEMONADE_TIMESTAMP.match(line)
        if m:
            timestamp = m.group(1)

    warning_override = (
        RE_WARNING_MARKER.search(line)
        or RE_EXPECTED_DETECTION_ERROR.search(line)
    )

    if warning_override:
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.WARNING,
            message=line, raw=line, icon="⚠️"
        )
    if RE_ERROR.search(line):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.ERROR,
            message=line, raw=line, icon="❌"
        )
    if RE_WARNING.search(line):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.WARNING,
            message=line, raw=line, icon="⚠️"
        )
    if RE_UPDATE_EVENT.search(line):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.UPDATE,
            message=line, raw=line, icon="⬆️"
        )
    if RE_BACKEND_EVENT.search(line):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.BACKEND,
            message=line, raw=line, icon="🧩"
        )
    if (
        RE_PROMPT_EVAL.search(line)
        or RE_GENERATION.search(line)
        or RE_TOTAL_TIME.search(line)
        or RE_TELEMETRY_INPUT.search(line)
        or RE_TELEMETRY_OUTPUT.search(line)
        or RE_TELEMETRY_TTFT.search(line)
        or RE_TELEMETRY_TPS.search(line)
    ):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.PERFORMANCE,
            message=line, raw=line, icon="📊"
        )
    if RE_MODEL_LOADED.search(line):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.MODEL,
            message=line, raw=line, icon="🧠"
        )
    if RE_SLOT_RELEASED.search(line):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.SLOT,
            message=line, raw=line, icon="✅"
        )
    if RE_SLOT_PROCESSING.search(line):
        return LogEntry(
            timestamp=timestamp, level=LogEntryLevel.GENERATION,
            message=line, raw=line, icon="🔄"
        )

    return LogEntry(
        timestamp=timestamp, level=LogEntryLevel.INFO,
        message=line, raw=line, icon="ℹ️"
    )


# ── Multi-record telemetry extraction ──────────────────────

# parse_last_task() above collapses the journal window to a single task, so any
# inference that finished between two polls is lost. The helpers below walk the
# same window and yield every completed record instead, which is what the
# long-run performance store needs.

@dataclass
class TaskTelemetryRecord:
    """One completed inference recovered from the journal."""

    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    ttft_seconds: float
    generation_tps: float
    prompt_eval_tps: float
    total_duration_seconds: float
    # False when none of the record's own lines carried a timestamp and
    # `timestamp` is the time it was read. It cannot be told apart by time.
    dated: bool = True
    # True when the time is journald's, not Lemonade's: legacy per-field
    # records have no timestamp of their own.
    journal_dated: bool = False

    @property
    def dedup_key(self) -> tuple[str, str, int, int]:
        """Identity of a record, so the same inference is stored only once."""
        return (self.timestamp, self.model, self.input_tokens, self.output_tokens)


class JournalReadError(RuntimeError):
    """The journal could not be read, as opposed to holding no records."""


def parse_task_records(
    service: str = "lemond.service",
    n_lines: int = 500,
    timeout: float = 10,
) -> list[TaskTelemetryRecord]:
    """Return every completed task in the journal window, oldest first.

    The journal is read as JSON so every line comes with the time journald
    received it. Legacy per-field records carry no timestamp of their own,
    and without that time they could only be dated by when they were read.

    Raises JournalReadError when the journal cannot be read, so the sampler
    reports it instead of recording nothing without a word. --system makes
    journalctl fail when the user may not read the system journal; without
    it, journalctl shows only the user's own journal and succeeds with no
    entries for lemond.service.
    """
    command = [
        "journalctl", "--system", "-u", service, "-n", str(n_lines),
        "-o", "json", "--output-fields=MESSAGE", "--no-pager",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise JournalReadError(f"journalctl could not be run: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        raise JournalReadError(
            f"journalctl exited with status {result.returncode}"
            + (f": {detail[0]}" if detail else "")
        )
    if not result.stdout.strip():
        return []

    messages, journal_times = _journal_messages(result.stdout)
    if not messages:
        raise JournalReadError("journalctl output was not the JSON it was asked for")
    return extract_task_records(messages, journal_times)


def _journal_messages(output: str) -> tuple[list[str], list[str | None]]:
    """Messages and their journald receive times from `journalctl -o json`."""
    messages: list[str] = []
    times: list[str | None] = []
    for raw_line in output.splitlines():
        try:
            payload = json.loads(raw_line)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        message = payload.get("MESSAGE")
        if isinstance(message, list):
            # journald hands over messages that are not valid UTF-8 as bytes.
            try:
                message = bytes(message).decode("utf-8", errors="replace")
            except (TypeError, ValueError):
                continue
        if not isinstance(message, str):
            continue
        messages.append(message)
        times.append(_journal_timestamp(payload.get("__REALTIME_TIMESTAMP")))
    return messages, times


def extract_task_records(
    lines: list[str],
    journal_times: list[str | None] | None = None,
) -> list[TaskTelemetryRecord]:
    """Pull every telemetry record out of raw journal lines, oldest first.

    Handles both spellings parse_last_task() accepts: the Lemonade 11.7
    single-line record, where all fields share one line, and the legacy
    per-field lines (Input tokens, Output tokens, TTFT, TPS), where they
    arrive one after another.

    The result for a record must not depend on where the journal window
    starts or ends, or the same inference would be stored twice as the
    window moves:

    * an input-token count always starts a new record, so a window that
      starts inside a record cannot shift the fields of later ones;
    * a record without an input-token count lost its start to the window
      edge and is dropped;
    * a line with nothing new for a record ends it, so one record never
      takes the fields of another whose input-token line was lost;
    * the last record is kept only once all four fields are there, since
      the rest of it may still be on its way to the journal;
    * a record is dated by its own lines only, never by an earlier line:
      by Lemonade's own timestamp where the line has one, otherwise by the
      time journald received the line (`journal_times`, one per line).

    The records are split as for parse_last_task(); see _telemetry_records().
    """
    records: list[TaskTelemetryRecord] = []
    telemetry = _telemetry_records(lines)
    for position, found in enumerate(telemetry):
        if (
            position == len(telemetry) - 1
            and not found.closed
            and not all(key in found.fields for key in _RECORD_FIELDS)
        ):
            continue
        # TTFT is kept as logged: Lemonade 2026.45 reports milliseconds
        # (0.485s), and the prompt rate is derived from it.
        pending: dict[str, object] = dict(found.fields)
        for index in found.lines:
            received = journal_times[index] if journal_times and index < len(journal_times) else None
            own_timestamp = _line_timestamp(lines[index], received)
            if own_timestamp or received:
                pending["timestamp"] = own_timestamp or received
                pending["journal_dated"] = own_timestamp is None
                break
        record = _build_task_record(pending)
        if record is not None:
            records.append(record)
    return records


# The fields every telemetry record carries, in both spellings.
_RECORD_FIELDS = ("input_tokens", "output_tokens", "ttft_seconds", "generation_tps")


def _build_task_record(pending: dict[str, object]) -> TaskTelemetryRecord | None:
    """Turn an accumulated field set into a record, or None if unusable."""
    input_tokens = pending.get("input_tokens")
    output_tokens = pending.get("output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    if output_tokens <= 0:
        return None

    ttft = pending.get("ttft_seconds")
    generation_tps = pending.get("generation_tps")
    ttft_seconds = float(ttft) if isinstance(ttft, (int, float)) else 0.0
    gen_tps = float(generation_tps) if isinstance(generation_tps, (int, float)) else 0.0

    # Same derivations parse_last_task() applies: the single-line telemetry
    # reports neither the prompt-eval rate nor the wall-clock duration, because
    # the llama.cpp timing lines they came from are silenced at log-verbosity 0.
    prompt_eval_tps = round(input_tokens / ttft_seconds, 2) if ttft_seconds else 0.0
    total_seconds = round(ttft_seconds + output_tokens / gen_tps, 1) if gen_tps else 0.0

    timestamp = pending.get("timestamp")
    dated = isinstance(timestamp, str) and bool(timestamp)
    if not dated:
        timestamp = datetime.now(UTC).isoformat()

    model = pending.get("model")

    return TaskTelemetryRecord(
        timestamp=timestamp,
        model=model if isinstance(model, str) and model else "unknown",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        ttft_seconds=ttft_seconds,
        generation_tps=gen_tps,
        prompt_eval_tps=prompt_eval_tps,
        total_duration_seconds=total_seconds,
        dated=dated,
        journal_dated=dated and bool(pending.get("journal_dated")),
    )


def _line_timestamp(line: str, received: str | None = None) -> str | None:
    """Normalise a journal line's leading timestamp to an aware ISO string.

    `received` is when journald received the line, if known. It settles
    Lemonade's local times that occur twice when the clocks go back.
    """
    match = RE_TIMESTAMP.match(line)
    if match:
        raw = match.group(1)
        try:
            return _as_utc(datetime.fromisoformat(raw)).isoformat()
        except ValueError:
            # Syslog-style "Mon 22 10:00:48" carries no year; it cannot be
            # resolved to an instant, so the caller falls back to now.
            return None

    match = RE_LEMONADE_TIMESTAMP.match(line)
    if not match:
        return None
    try:
        # Lemonade stamps its own lines in host local time with no offset.
        parsed = datetime.fromisoformat(match.group(1).replace(" ", "T"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = _local_instant(parsed, received)
    return _as_utc(parsed).isoformat()


def _local_instant(naive: datetime, received: str | None) -> datetime:
    """Place a host-local time without offset on the timeline.

    In the hour the clocks go back the same local time occurs twice, and
    astimezone() alone always picks the first. The time journald received the
    line tells which one it was. Outside that hour both readings agree, so
    Lemonade's own timestamp, and with it the record's identity, is unchanged.
    """
    first = naive.replace(fold=0).astimezone()
    second = naive.replace(fold=1).astimezone()
    if first == second or received is None:
        return first
    try:
        reference = datetime.fromisoformat(received)
    except ValueError:
        return first
    return min((first, second), key=lambda candidate: abs(candidate - reference))
