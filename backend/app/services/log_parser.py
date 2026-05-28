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
import re
import subprocess
from datetime import datetime

from app.models.schemas import (
    LogEntry,
    LogEntryLevel,
    LastTaskStats,
    FinishReason,
    FinishReasonConfidence,
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

RE_TELEMETRY_INPUT = re.compile(r"\bInput tokens:\s*(\d+)", re.IGNORECASE)
RE_TELEMETRY_OUTPUT = re.compile(r"\bOutput tokens:\s*(\d+)", re.IGNORECASE)
RE_TELEMETRY_TTFT = re.compile(r"\bTTFT\s*\(s\):\s*([\d.]+)", re.IGNORECASE)
RE_TELEMETRY_TPS = re.compile(r"\bTPS:\s*([\d.]+)", re.IGNORECASE)

RE_MODEL_LOADED = re.compile(r"model\s+loaded|all\s+slots\s+are\s+idle", re.IGNORECASE)

RE_ERROR = re.compile(r"\b(?:error|exception|fail|fatal)\b", re.IGNORECASE)
RE_WARNING = re.compile(r"\b(?:warn|warning|timeout|truncat)\b", re.IGNORECASE)

RE_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.]+[+-]\d{2}:\d{2}|\w{3}\s+\d+\s+[\d:]+)")
RE_LEMONADE_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}\s+[\d:.]+)")


def get_recent_logs(
    service: str = "lemond.service",
    n_lines: int = 100
) -> RecentLogsResponse:
    """Get recent log entries from journalctl, parsed into structured format."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", service, "-n", str(n_lines),
             "-o", "cat", "--no-pager"],
            capture_output=True, text=True, timeout=10
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


def parse_last_task(
    service: str = "lemond.service",
    n_lines: int = 200,
    configured_max_tokens: int | None = None,
) -> LastTaskStats:
    """Parse the most recent completed task from journalctl logs."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", service, "-n", str(n_lines),
             "-o", "cat", "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0 or not result.stdout.strip():
            return LastTaskStats(available=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return LastTaskStats(available=False)

    lines = result.stdout.strip().split("\n")

    stats = LastTaskStats(available=True, raw_log_lines=lines[-50:])

    for line in reversed(lines):
        m = RE_TELEMETRY_INPUT.search(line)
        if m and stats.input_tokens is None:
            stats.input_tokens = int(m.group(1))

        m = RE_TELEMETRY_OUTPUT.search(line)
        if m and stats.output_tokens is None:
            stats.output_tokens = int(m.group(1))

        m = RE_TELEMETRY_TTFT.search(line)
        if m and stats.ttft_seconds is None:
            stats.ttft_seconds = round(float(m.group(1)), 2)

        m = RE_TELEMETRY_TPS.search(line)
        if m and stats.generation_tps is None:
            stats.generation_tps = float(m.group(1))

        m = RE_SLOT_TRUNCATED.search(line)
        if m and stats.truncated is None:
            stats.truncated = bool(int(m.group(1)))

        m = RE_PROMPT_EVAL.search(line)
        if m and stats.input_tokens is None:
            stats.input_tokens = int(m.group(1))
            stats.prompt_eval_tps = float(m.group(2))
        elif m and stats.prompt_eval_tps is None:
            stats.prompt_eval_tps = float(m.group(2))

        m = RE_GENERATION.search(line)
        if m and stats.output_tokens is None:
            gen_time_ms = float(m.group(1))
            stats.output_tokens = int(m.group(2))
            stats.generation_tps = float(m.group(3))

        m = RE_TOTAL_TIME.search(line)
        if m and stats.total_duration_seconds is None:
            stats.total_duration_seconds = round(float(m.group(1)) / 1000, 1)

    if stats.ttft_seconds is None and stats.prompt_eval_tps and stats.input_tokens:
        stats.ttft_seconds = round(stats.input_tokens / stats.prompt_eval_tps, 2)

    stats.finish_reason = _infer_finish_reason(stats, configured_max_tokens)

    return stats


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
