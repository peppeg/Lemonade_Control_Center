"""Run evidence smoke tests and local evidence storage."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from pydantic import ValidationError

from app.models.completions import CompletionRequest
from app.models.schemas import LoadModelRequest, LoadModelResponse, RunEvidenceSeed, SmokeTestRequest, SmokeTestResponse
from app.services.completion_runner import CompletionRunner
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
        completion_runner: CompletionRunner,
        storage: RunEvidenceStorage | None = None,
    ) -> None:
        self.completion_runner = completion_runner
        self.storage = storage or RunEvidenceStorage()

    async def run(self, request: SmokeTestRequest) -> SmokeTestResponse:
        before_hardware = _safe_hardware_snapshot()
        before_process = _safe_process_snapshot()

        completion_request = CompletionRequest(
            model=request.model_name,
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout_seconds=request.app_timeout_seconds,
            stop_sequences=request.stop_sequences,
        )
        result = await self.completion_runner.run(completion_request)

        after_hardware = _safe_hardware_snapshot()
        after_process = _safe_process_snapshot()
        process = after_process or before_process
        warnings: list[str] = []

        if not result.success:
            warnings.append("Smoke request failed; check Lemonade health, loaded model state, and logs.")
        warnings.extend(result.warnings)
        if not process:
            warnings.append("No llama-server process evidence was available for this run.")

        evidence = RunEvidenceSeed(
            id=str(uuid.uuid4()),
            model_name=request.model_name,
            prompt=request.prompt,
            response_text=result.response_text,
            reasoning_text=result.reasoning_text,
            success=result.success,
            error=result.error.message if result.error else None,
            completion_error_kind=result.error.kind if result.error else None,
            completion_endpoint=result.endpoint,
            token_count_source=result.token_count_source,
            request_max_tokens=request.max_tokens,
            request_temperature=request.temperature,
            request_timeout_seconds=request.app_timeout_seconds,
            request_stop_sequences=request.stop_sequences,
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


class LoadEvidenceRecorder:
    """Records a load attempt as local operator evidence."""

    def __init__(self, storage: RunEvidenceStorage | None = None) -> None:
        self.storage = storage or RunEvidenceStorage()

    def start(self) -> dict:
        return {
            "started_at": time.monotonic(),
            "hardware": _safe_hardware_snapshot(),
            "process": _safe_process_snapshot(),
        }

    def record_response(
        self,
        request: LoadModelRequest,
        response: LoadModelResponse,
        started: dict,
    ) -> RunEvidenceSeed:
        after_hardware = _safe_hardware_snapshot()
        after_process = _safe_process_snapshot()
        process = after_process or started.get("process")
        warnings = _load_warnings(request, response, process)

        evidence = RunEvidenceSeed(
            id=str(uuid.uuid4()),
            kind="load_attempt",
            model_name=request.model_name,
            success=response.success,
            error=None if response.success else response.message,
            load_message=response.message,
            requested_backend=request.llamacpp_backend,
            requested_ctx_size=request.ctx_size,
            requested_llamacpp_args=request.llamacpp_args,
            merge_args=request.merge_args,
            save_options=request.save_options,
            total_seconds=round(time.monotonic() - started["started_at"], 2),
            observed_pid=process["pid"] if process else None,
            observed_backend=process["backend"] if process else None,
            observed_ctx_size=process["ctx_size"] if process else None,
            process_rss_gb=process["rss_gb"] if process else None,
            ram_used_before_gb=started["hardware"]["ram_used_gb"] if started.get("hardware") else None,
            ram_used_after_gb=after_hardware["ram_used_gb"] if after_hardware else None,
            swap_used_before_gb=started["hardware"]["swap_used_gb"] if started.get("hardware") else None,
            swap_used_after_gb=after_hardware["swap_used_gb"] if after_hardware else None,
            warnings=warnings,
        )
        self.storage.add(evidence)
        return evidence

    def record_exception(
        self,
        request: LoadModelRequest,
        exc: Exception,
        started: dict,
    ) -> RunEvidenceSeed:
        response = LoadModelResponse(success=False, message=str(exc), raw=None)
        return self.record_response(request, response, started)


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


def _load_warnings(
    request: LoadModelRequest,
    response: LoadModelResponse,
    process: dict | None,
) -> list[str]:
    warnings: list[str] = []
    if not response.success:
        warnings.append("Load request failed; check Lemonade health and recent logs.")
        return warnings
    if not process:
        warnings.append("Model loaded but no llama-server process evidence was available.")
        return warnings
    if request.llamacpp_backend and process.get("backend") and request.llamacpp_backend != process["backend"]:
        warnings.append(f"Requested backend {request.llamacpp_backend}, observed {process['backend']}.")
    if request.ctx_size and process.get("ctx_size") and request.ctx_size != process["ctx_size"]:
        warnings.append(f"Requested ctx {request.ctx_size}, observed {process['ctx_size']}.")
    return warnings
