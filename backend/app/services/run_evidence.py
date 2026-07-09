"""Run evidence smoke tests and local evidence storage."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from pydantic import ValidationError

from app.models.schemas import RunEvidenceSeed, SmokeTestRequest, SmokeTestResponse
from app.services.bench.models import BenchPrompt
from app.services.bench.runner import BenchRunner
from app.services.hardware import get_hardware_info
from app.services.process import find_llama_server

EVIDENCE_FILE = Path(__file__).parent.parent / "data" / "run_evidence.json"


class RunEvidenceStorage:
    """Stores a small rolling set of local evidence records."""

    def __init__(self, path: Path = EVIDENCE_FILE, max_results: int = 50) -> None:
        self.path = path
        self.max_results = max_results

    def add(self, evidence: RunEvidenceSeed) -> None:
        results = self.get_all()
        results.insert(0, evidence)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([item.model_dump(mode="json") for item in results[: self.max_results]], indent=2),
            encoding="utf-8",
        )

    def get_all(self, model_name: str | None = None) -> list[RunEvidenceSeed]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return []
        if not isinstance(raw, list):
            return []
        results: list[RunEvidenceSeed] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                results.append(RunEvidenceSeed.model_validate(item))
            except ValidationError:
                continue
        if model_name:
            results = [item for item in results if item.model_name == model_name]
        return results[: self.max_results]


class SmokeTestRunner:
    """Runs a minimal post-load request and records operator evidence."""

    def __init__(
        self,
        *,
        bench_runner: BenchRunner | None = None,
        storage: RunEvidenceStorage | None = None,
    ) -> None:
        self.bench_runner = bench_runner or BenchRunner()
        self.storage = storage or RunEvidenceStorage()

    async def run(self, request: SmokeTestRequest) -> SmokeTestResponse:
        before_hardware = _safe_hardware_snapshot()
        before_process = _safe_process_snapshot()

        prompt = BenchPrompt(
            id="post_load_smoke",
            name="Post-load Smoke Test",
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            expected_format="text",
            tags=["smoke", "run-evidence"],
        )
        result = await self.bench_runner.run_prompt(prompt, request.model_name)

        after_hardware = _safe_hardware_snapshot()
        after_process = _safe_process_snapshot()
        process = after_process or before_process
        warnings: list[str] = []

        if result.error:
            warnings.append("Smoke request failed; check Lemonade health, loaded model state, and logs.")
        if not process:
            warnings.append("No llama-server process evidence was available for this run.")

        evidence = RunEvidenceSeed(
            id=str(uuid.uuid4()),
            model_name=request.model_name,
            prompt=request.prompt,
            response_text=result.response_full,
            success=result.error is None,
            error=result.error,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            prompt_eval_tps=result.prompt_eval_tps,
            generation_tps=result.generation_tps,
            ttft_seconds=result.ttft_seconds,
            total_seconds=result.total_seconds,
            finish_reason=result.finish_reason,
            finish_confidence=result.finish_confidence,
            observed_pid=process["pid"] if process else None,
            observed_backend=process["backend"] if process else None,
            observed_ctx_size=process["ctx_size"] if process else None,
            process_rss_gb=process["rss_gb"] if process else None,
            ram_used_before_gb=before_hardware["ram_used_gb"] if before_hardware else None,
            ram_used_after_gb=after_hardware["ram_used_gb"] if after_hardware else None,
            swap_used_before_gb=before_hardware["swap_used_gb"] if before_hardware else None,
            swap_used_after_gb=after_hardware["swap_used_gb"] if after_hardware else None,
            warnings=warnings,
        )
        self.storage.add(evidence)

        return SmokeTestResponse(
            success=evidence.success,
            message="Smoke test completed." if evidence.success else "Smoke test failed.",
            evidence=evidence,
        )


def _safe_hardware_snapshot() -> dict | None:
    try:
        hardware = get_hardware_info()
    except Exception:
        return None
    return {
        "ram_used_gb": hardware.ram_used_gb,
        "swap_used_gb": hardware.swap_used_gb,
    }


def _safe_process_snapshot() -> dict | None:
    try:
        info = find_llama_server()
    except Exception:
        return None
    if not info.found or not info.process:
        return None
    return {
        "pid": info.process.pid,
        "rss_gb": info.process.rss_gb,
        "backend": info.params.backend if info.params else None,
        "ctx_size": info.params.ctx_size if info.params else None,
    }
