"""Task performance history built from the latest parsed log task."""
from __future__ import annotations

import csv
import io
import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.capabilities import capabilities
from app.services.log_parser import parse_last_task

HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "task_history.json"


@dataclass
class TaskRecord:
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    prompt_tps: float
    gen_tps: float
    ttft_seconds: float
    total_seconds: float
    finish_reason: str
    finish_confidence: str


class TaskHistory:
    def __init__(self, max_tasks: int = 50) -> None:
        self._tasks: deque[TaskRecord] = deque(maxlen=max_tasks)
        self._seen_keys: set[str] = set()
        self._load()

    def refresh_from_logs(self) -> None:
        if not capabilities.cmd_journalctl:
            return
        task = parse_last_task()
        if not task.available or not task.output_tokens:
            return
        key = "|".join(
            [
                str(task.input_tokens),
                str(task.output_tokens),
                str(task.generation_tps),
                str(task.total_duration_seconds),
            ]
        )
        if key in self._seen_keys:
            return
        record = TaskRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model="current",
            input_tokens=task.input_tokens or 0,
            output_tokens=task.output_tokens or 0,
            prompt_tps=task.prompt_eval_tps or 0,
            gen_tps=task.generation_tps or 0,
            ttft_seconds=task.ttft_seconds or 0,
            total_seconds=task.total_duration_seconds or 0,
            finish_reason=task.finish_reason.reason,
            finish_confidence=str(task.finish_reason.confidence),
        )
        self._tasks.append(record)
        self._seen_keys.add(key)
        self._save()

    def get_recent(self, n: int = 20) -> list[dict]:
        self.refresh_from_logs()
        return [asdict(task) for task in list(self._tasks)[-n:]]

    def clear(self) -> None:
        self._tasks.clear()
        self._seen_keys.clear()
        self._save()

    def export_csv(self) -> str:
        self.refresh_from_logs()
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(TaskRecord.__annotations__.keys()))
        writer.writeheader()
        for task in self._tasks:
            writer.writerow(asdict(task))
        return output.getvalue()

    def _load(self) -> None:
        if not HISTORY_FILE.exists():
            return
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            for item in data.get("tasks", []):
                task = TaskRecord(**item)
                self._tasks.append(task)
                self._seen_keys.add(f"{task.input_tokens}|{task.output_tokens}|{task.gen_tps}|{task.total_seconds}")
        except (OSError, TypeError, ValueError):
            pass

    def _save(self) -> None:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(
            json.dumps({"tasks": [asdict(task) for task in self._tasks]}, indent=2),
            encoding="utf-8",
        )
