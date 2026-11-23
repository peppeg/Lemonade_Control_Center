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

RE_PROMPT_EVAL = re.compile(
    r"prompt eval time\s*=\s*[\d.]+\s*ms\s*/\s*(\d+)\s*tokens?\s*"
    r"\([^)]*,\s*([\d.]+)\s*tokens?(?:/s|\s+per\s+second)\)"
)

RE_GENERATION = re.compile(
    r"(?:generation|eval) (?:eval )?time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens?\s*"
    r"\([^)]*,\s*([\d.]+)\s*tokens?(?:/s|\s+per\s+second)\)"
)

RE_TOTAL_TIME = re.compile(
    r"total time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens?"
)

RE_SLOT_RELEASED = re.compile(r"slot\s+(?:released|freed)", re.IGNORECASE)
RE_SLOT_PROCESSING = re.compile(r"slot\s+(?:is\s+)?processing", re.IGNORECASE)
RE_SLOT_TRUNCATED = re.compile(r"truncated\s*=\s*(\d+)", re.IGNORECASE)

RE_TELEMETRY_INPUT = re.compile(
    r"(?:\bInput tokens:\s*|\bin=)(\d+)", re.IGNORECASE)
RE_TELEMETRY_OUTPUT = re.compile(
    r"(?:\bOutput tokens:\s*|\bout=)(\d+)", re.IGNORECASE)
RE_TELEMETRY_TTFT = re.compile(
    r"(?:\bTTFT\s*\(s\):\s*|\bttft=)([\d.]+)", re.IGNORECASE)
RE_TELEMETRY_TPS = re.compile(
    r"(?:\bTPS:\s*|\btps=)([\d.]+)", re.IGNORECASE)
RE_TELEMETRY_MODEL = re.compile(
    r"Inference completed:.*?\bmodel=([^,\s]+)", re.IGNORECASE)

RE_SLOT_TASK = re.compile(r"\bid\s+(\d+)\s*\|\s*task\s+(\d+)")

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
    """Fill `stats` from the newest task only.

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

    A record is one `Inference completed` line, or the older format with one
    field per line. Both begin with the input tokens. The range goes from the
    end of the previous record to the end of this one.
    """
    record: dict = {}
    start = end = 0
    for index, line in enumerate(lines):
        fields: dict = {}
        if m := RE_TELEMETRY_INPUT.search(line):
            fields["input_tokens"] = int(m.group(1))
        if m := RE_TELEMETRY_OUTPUT.search(line):
            fields["output_tokens"] = int(m.group(1))
        if m := RE_TELEMETRY_TTFT.search(line):
            fields["ttft_seconds"] = round(float(m.group(1)), 2)
        if m := RE_TELEMETRY_TPS.search(line):
            fields["generation_tps"] = float(m.group(1))
        if m := RE_TELEMETRY_MODEL.search(line):
            fields["model"] = m.group(1)
            fields["completed_at"] = _lemonade_timestamp_iso(line)

        if "input_tokens" in fields:
            start, record = end, {}
        elif not record or fields.keys() <= record.keys():
            continue
        record = fields | record
        end = index + 1
    return record, start, end


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

    stats.finish_reason = _infer_finish_reason(stats, configured_max_tokens)

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


def _infer_finish_reason(
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
