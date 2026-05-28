"""Persistent Bench Lab result storage."""
from __future__ import annotations

import csv
import io
import json
from collections import deque
from pathlib import Path

from app.services.bench.models import BenchResult, SuiteResult

RESULTS_FILE = Path(__file__).parent.parent.parent / "data" / "bench_results.json"


class BenchStorage:
    def __init__(self, max_suite_results: int = 100, max_quick_results: int = 50) -> None:
        self._suite_results: deque[dict] = deque(maxlen=max_suite_results)
        self._quick_results: deque[dict] = deque(maxlen=max_quick_results)
        self._load()

    def add_suite_result(self, result: SuiteResult) -> None:
        self._suite_results.append(result.model_dump(mode="json"))
        self._save()

    def add_quick_result(self, result: BenchResult) -> None:
        data = result.model_dump(mode="json")
        data["suite_id"] = "quick"
        data["suite_name"] = "Quick Test"
        self._quick_results.append(data)
        self._save()

    def get_all(self, model: str | None = None, suite: str | None = None) -> list[dict]:
        results = list(self._suite_results) + list(self._quick_results)
        if model:
            results = [result for result in results if result.get("model") == model]
        if suite:
            results = [result for result in results if result.get("suite_id") == suite]
        return sorted(results, key=lambda result: result.get("timestamp", ""), reverse=True)

    def export_json(self) -> str:
        return json.dumps(self.get_all(), indent=2)

    def export_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "model", "suite", "avg_tps", "avg_ttft", "tokens", "errors"])
        for result in self.get_all():
            writer.writerow([
                result.get("timestamp", ""),
                result.get("model", ""),
                result.get("suite_name", result.get("prompt_name", "")),
                result.get("avg_gen_tps", result.get("generation_tps", 0)),
                result.get("avg_ttft", result.get("ttft_seconds", 0)),
                result.get("total_tokens", result.get("output_tokens", 0)),
                result.get("error_count", 1 if result.get("error") else 0),
            ])
        return output.getvalue()

    def export_markdown(self) -> str:
        lines = ["# Bench Lab Results", ""]
        for result in self.get_all():
            title = result.get("suite_name", result.get("prompt_name", "Result"))
            lines.extend([
                f"## {title} - {result.get('model', 'unknown')}",
                f"- Timestamp: {result.get('timestamp', '')}",
                f"- TPS: {result.get('avg_gen_tps', result.get('generation_tps', 0))}",
                f"- TTFT: {result.get('avg_ttft', result.get('ttft_seconds', 0))}s",
                f"- Tokens: {result.get('total_tokens', result.get('output_tokens', 0))}",
                "",
            ])
        return "\n".join(lines)

    def clear(self) -> None:
        self._suite_results.clear()
        self._quick_results.clear()
        self._save()

    def _load(self) -> None:
        if not RESULTS_FILE.exists():
            return
        try:
            data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
            self._suite_results.extend(data.get("suites", []))
            self._quick_results.extend(data.get("quick", []))
        except (OSError, TypeError, ValueError):
            pass

    def _save(self) -> None:
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_FILE.write_text(
            json.dumps({"suites": list(self._suite_results), "quick": list(self._quick_results)}, indent=2),
            encoding="utf-8",
        )
