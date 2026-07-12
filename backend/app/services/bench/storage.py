"""Persistent Bench Lab result storage."""
from __future__ import annotations

import csv
import io
import json
import uuid
from collections import deque
from pathlib import Path

from app.services.bench.models import BenchAnnotationRequest, BenchComparison, BenchResult, SuiteResult

RESULTS_FILE = Path(__file__).parent.parent.parent / "data" / "bench_results.json"


class BenchStorage:
    def __init__(self, path: Path = RESULTS_FILE, max_suite_results: int = 100, max_quick_results: int = 50) -> None:
        self.path = path
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
        writer.writerow(["timestamp", "model", "profile", "suite", "avg_tps", "avg_ttft", "tokens", "errors", "quality", "notes"])
        for result in self.get_all():
            writer.writerow([
                result.get("timestamp", ""),
                result.get("model", ""),
                result.get("workflow_profile_name", ""),
                result.get("suite_name", result.get("prompt_name", "")),
                result.get("avg_gen_tps", result.get("generation_tps", 0)),
                result.get("avg_ttft", result.get("ttft_seconds", 0)),
                result.get("total_tokens", result.get("output_tokens", 0)),
                result.get("error_count", 1 if result.get("error") else 0),
                result.get("manual_quality_score", ""),
                result.get("manual_notes", ""),
            ])
        return output.getvalue()

    def export_markdown(self) -> str:
        lines = ["# Bench Lab Results", ""]
        for result in self.get_all():
            title = result.get("suite_name", result.get("prompt_name", "Result"))
            lines.extend([
                f"## {title} - {result.get('model', 'unknown')} / {result.get('workflow_profile_name') or 'no profile'}",
                f"- Timestamp: {result.get('timestamp', '')}",
                f"- TPS: {result.get('avg_gen_tps', result.get('generation_tps', 0))}",
                f"- TTFT: {result.get('avg_ttft', result.get('ttft_seconds', 0))}s",
                f"- Tokens: {result.get('total_tokens', result.get('output_tokens', 0))}",
                f"- Runtime: {result.get('runtime_label') or result.get('runtime_id') or 'unavailable'}",
                f"- Quality: {result.get('manual_quality_score') or 'unscored'}",
                f"- Notes: {result.get('manual_notes') or 'none'}",
                "",
            ])
        return "\n".join(lines)

    def clear(self) -> None:
        self._suite_results.clear()
        self._quick_results.clear()
        self._save()

    def annotate(self, result_id: str, request: BenchAnnotationRequest) -> dict | None:
        for collection in (self._suite_results, self._quick_results):
            for result in collection:
                if result.get("id") == result_id:
                    result["manual_quality_score"] = request.manual_quality_score
                    result["manual_notes"] = request.manual_notes
                    self._save()
                    return result
        return None

    def compare(self, result_ids: list[str]) -> BenchComparison:
        selected = [result for result in self.get_all() if result.get("id") in result_ids and "results" in result]
        if len(selected) < 2:
            raise ValueError("Select at least two stored suite results.")
        suites = {result.get("suite_id") for result in selected}
        if len(suites) != 1:
            raise ValueError("Comparison results must use the same suite.")
        if any(not result.get("workflow_profile_id") for result in selected):
            raise ValueError("Comparison results must include an applied workflow profile.")
        if any(
            result.get("observed_model_name")
            and result.get("observed_model_name") != result.get("requested_model_name", result.get("model"))
            for result in selected
        ):
            raise ValueError("Comparison results contain a requested/observed model mismatch.")
        parsed = [SuiteResult.model_validate(result) for result in selected]
        return BenchComparison(
            suite_id=parsed[0].suite_id,
            suite_name=parsed[0].suite_name,
            result_ids=[result.id for result in parsed],
            results=parsed,
        )

    def export_comparison_markdown(self, result_ids: list[str]) -> str:
        comparison = self.compare(result_ids)
        lines = [f"# Bench Comparison: {comparison.suite_name}", ""]
        lines.append("| Model | Profile | Avg TPS | Avg TTFT | Tokens | Errors | Quality |")
        lines.append("|---|---|---:|---:|---:|---:|---:|")
        for result in comparison.results:
            lines.append(
                f"| {result.model} | {result.workflow_profile_name or 'none'} | {result.avg_gen_tps} | "
                f"{result.avg_ttft}s | {result.total_tokens} | {result.error_count} | "
                f"{result.manual_quality_score or 'unscored'} |"
            )
        lines.extend(["", "## Operator Notes", ""])
        for result in comparison.results:
            lines.append(f"- **{result.model} / {result.workflow_profile_name or 'none'}:** {result.manual_notes or 'none'}")
        return "\n".join(lines) + "\n"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            suites = data.get("suites", [])
            quick = data.get("quick", [])
            changed = False
            for result in [*suites, *quick]:
                if isinstance(result, dict) and not result.get("id"):
                    result["id"] = str(uuid.uuid4())
                    changed = True
                if isinstance(result, dict):
                    for prompt in result.get("results", []):
                        if isinstance(prompt, dict) and not prompt.get("id"):
                            prompt["id"] = str(uuid.uuid4())
                            changed = True
            self._suite_results.extend(suites)
            self._quick_results.extend(quick)
            if changed:
                self._save()
        except (OSError, TypeError, ValueError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"suites": list(self._suite_results), "quick": list(self._quick_results)}, indent=2),
            encoding="utf-8",
        )
