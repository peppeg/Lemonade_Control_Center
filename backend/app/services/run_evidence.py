"""Run evidence smoke tests and local evidence storage."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from app.models.completions import CompletionRequest
from app.models.schemas import LoadModelRequest, LoadModelResponse, RunEvidenceSeed, SmokeTestRequest, SmokeTestResponse
from app.models.setup import RuntimeConfig
from app.services.completion_runner import CompletionRunner
from app.services.hardware import get_hardware_info
from app.services.log_parser import get_logs_for_window
from app.services.process import find_llama_server
from app.services.telemetry import TelemetryManager

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

    def get_all(
        self,
        model_name: str | None = None,
        kind: str | None = None,
        success: bool | None = None,
        runtime_id: str | None = None,
        workflow_profile_id: str | None = None,
    ) -> list[RunEvidenceSeed]:
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
        if kind:
            results = [item for item in results if item.kind == kind]
        if success is not None:
            results = [item for item in results if item.success is success]
        if runtime_id:
            results = [item for item in results if item.runtime_id == runtime_id]
        if workflow_profile_id:
            results = [item for item in results if item.workflow_profile_id == workflow_profile_id]
        return results[: self.max_results]

    def get(self, evidence_id: str) -> RunEvidenceSeed | None:
        return next((item for item in self.get_all() if item.id == evidence_id), None)


def render_evidence_json(evidence: RunEvidenceSeed) -> str:
    """Render one complete evidence record for local export."""
    return json.dumps(evidence.model_dump(mode="json"), indent=2)


def render_evidence_markdown(evidence: RunEvidenceSeed) -> str:
    """Render one evidence record as a readable operator report."""
    outcome = "passed" if evidence.success else "failed"
    lines = [
        "# LCC Run Evidence",
        "",
        f"- **ID:** `{evidence.id}`",
        f"- **Timestamp:** {evidence.timestamp.isoformat()}",
        f"- **Kind:** {evidence.kind}",
        f"- **Outcome:** {outcome}",
        f"- **Model:** `{evidence.model_name}`",
        f"- **Requested model:** `{evidence.requested_model_name or evidence.model_name}`",
        f"- **Observed model:** `{evidence.observed_model_name}`" if evidence.observed_model_name else "- **Observed model:** unavailable",
        "",
        "## LCC Identity",
        "",
        f"- **Runtime:** {evidence.runtime_label or 'unavailable'} ({evidence.runtime_id or 'unavailable'})",
        f"- **Server URL:** `{evidence.runtime_server_url}`" if evidence.runtime_server_url else "- **Server URL:** unavailable",
        f"- **Workflow profile:** {evidence.workflow_profile_name or 'unavailable'} ({evidence.workflow_profile_id or 'unavailable'})",
        "",
        "## Runtime",
        "",
        f"- **Backend:** {evidence.observed_backend or 'unavailable'}",
        f"- **Context:** {evidence.observed_ctx_size or 'unavailable'}",
        f"- **PID:** {evidence.observed_pid or 'unavailable'}",
        f"- **Process RSS:** {_format_gb(evidence.process_rss_gb)}",
        f"- **RAM used:** {_format_gb(evidence.ram_used_before_gb)} before / {_format_gb(evidence.ram_used_after_gb)} after",
        f"- **Swap used:** {_format_gb(evidence.swap_used_before_gb)} before / {_format_gb(evidence.swap_used_after_gb)} after",
        f"- **Duration:** {evidence.total_seconds:.3f} s",
    ]

    if evidence.kind == "smoke_test":
        lines.extend(
            [
                "",
                "## Completion",
                "",
                f"- **Endpoint:** {evidence.completion_endpoint or 'unavailable'}",
                f"- **TTFT:** {evidence.ttft_seconds:.3f} s",
                f"- **Prompt evaluation:** {evidence.prompt_eval_tps:.2f} tok/s",
                f"- **Generation:** {evidence.generation_tps:.2f} tok/s",
                f"- **Tokens:** {evidence.input_tokens} input / {evidence.output_tokens} output",
                f"- **Token source:** {evidence.token_count_source}",
                f"- **Finish:** {evidence.finish_reason} ({evidence.finish_confidence})",
                f"- **Error kind:** {evidence.completion_error_kind or 'none'}",
                f"- **Max tokens:** {evidence.request_max_tokens or 'unavailable'}",
                f"- **Temperature:** {_format_optional(evidence.request_temperature)}",
                f"- **Timeout:** {_format_seconds(evidence.request_timeout_seconds)}",
                f"- **Stop sequences:** {_format_list(evidence.request_stop_sequences)}",
                "",
                "## Prompt",
                "",
                "```text",
                evidence.prompt,
                "```",
                "",
                "## Response",
                "",
                "```text",
                evidence.response_text,
                "```",
            ]
        )
        if evidence.reasoning_text:
            lines.extend(["", "## Reasoning", "", "```text", evidence.reasoning_text, "```"])
    else:
        lines.extend(
            [
                "",
                "## Load Request",
                "",
                f"- **Requested backend:** {evidence.requested_backend or 'default'}",
                f"- **Requested context:** {evidence.requested_ctx_size or 'default'}",
                f"- **Merge args:** {_format_bool(evidence.merge_args)}",
                f"- **Save options:** {_format_bool(evidence.save_options)}",
                f"- **Message:** {evidence.load_message or 'unavailable'}",
                f"- **llama.cpp args:** {evidence.requested_llamacpp_args or 'none'}",
            ]
        )

    if evidence.error:
        lines.extend(["", "## Error", "", evidence.error])
    lines.extend(
        [
            "",
            "## Correlated Logs",
            "",
            f"- **Source:** {evidence.log_source}",
            f"- **Window start:** {_format_datetime(evidence.log_window_started_at)}",
            f"- **Window end:** {_format_datetime(evidence.log_window_ended_at)}",
        ]
    )
    if evidence.log_capture_error:
        lines.append(f"- **Capture error:** {evidence.log_capture_error}")
    if evidence.log_entries:
        lines.extend(["", "```text"])
        lines.extend(
            f"{entry.timestamp or 'unknown time'} [{entry.level.value.upper()}] {entry.message}"
            for entry in evidence.log_entries
        )
        lines.append("```")
    else:
        lines.extend(["", "No log entries were captured for this run window."])
    lines.extend(
        [
            "",
            "## Telemetry Providers",
            "",
            f"- **Accelerator ownership:** {evidence.accelerator_ownership}",
            f"- **Ownership note:** {evidence.accelerator_ownership_note}",
        ]
    )
    for sample in evidence.telemetry_samples:
        lines.append(f"- **{sample.provider_label} ({sample.phase}):** {sample.quality}")
        if sample.error:
            lines.append(f"  - Error: {sample.error}")
        for metric in sample.metrics:
            value = "unavailable" if metric.value is None else f"{metric.value}{metric.unit or ''}"
            lines.append(f"  - {metric.name}: {value} [{metric.quality}] ({metric.evidence})")
    if evidence.warnings:
        lines.extend(["", "## Warnings", "", *[f"- {warning}" for warning in evidence.warnings]])
    return "\n".join(lines) + "\n"


def _format_gb(value: float | None) -> str:
    return f"{value:.2f} GB" if value is not None else "unavailable"


def _format_bool(value: bool | None) -> str:
    if value is None:
        return "unavailable"
    return "yes" if value else "no"


def _format_optional(value: float | None) -> str:
    return str(value) if value is not None else "unavailable"


def _format_seconds(value: int | None) -> str:
    return f"{value} s" if value is not None else "unavailable"


def _format_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "unavailable"


class SmokeTestRunner:
    """Runs a minimal post-load request and records operator evidence."""

    def __init__(
        self,
        *,
        completion_runner: CompletionRunner,
        storage: RunEvidenceStorage | None = None,
        log_collector=None,
        runtime: RuntimeConfig | None = None,
        telemetry_manager: TelemetryManager | None = None,
    ) -> None:
        self.completion_runner = completion_runner
        self.storage = storage or RunEvidenceStorage()
        self.log_collector = log_collector or _safe_log_snapshot
        self.runtime = runtime
        self.telemetry_manager = telemetry_manager or TelemetryManager()

    async def run(self, request: SmokeTestRequest, observed_model_name: str | None = None) -> SmokeTestResponse:
        started_at = datetime.now(timezone.utc)
        telemetry_start = self.telemetry_manager.snapshot("start")
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
        telemetry_end = self.telemetry_manager.snapshot("end")
        ended_at = datetime.now(timezone.utc)
        log_capture = self.log_collector(started_at, ended_at)
        process = after_process or before_process
        warnings: list[str] = []

        if not result.success:
            warnings.append("Smoke request failed; check Lemonade health, loaded model state, and logs.")
        warnings.extend(result.warnings)
        if not process:
            warnings.append("No llama-server process evidence was available for this run.")
        if log_capture["error"]:
            warnings.append(log_capture["error"])

        evidence = RunEvidenceSeed(
            id=str(uuid.uuid4()),
            model_name=request.model_name,
            requested_model_name=request.model_name,
            observed_model_name=observed_model_name,
            **_identity_fields(self.runtime, request.workflow_profile_id, request.workflow_profile_name),
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
            log_window_started_at=started_at,
            log_window_ended_at=ended_at,
            log_source=log_capture["source"],
            log_entries=log_capture["entries"],
            log_capture_error=log_capture["error"],
            telemetry_samples=[*telemetry_start.samples, *telemetry_end.samples],
            accelerator_ownership=telemetry_end.accelerator_ownership,
            accelerator_ownership_note=telemetry_end.ownership_note,
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

    def __init__(
        self,
        storage: RunEvidenceStorage | None = None,
        log_collector=None,
        runtime: RuntimeConfig | None = None,
        telemetry_manager: TelemetryManager | None = None,
    ) -> None:
        self.storage = storage or RunEvidenceStorage()
        self.log_collector = log_collector or _safe_log_snapshot
        self.runtime = runtime
        self.telemetry_manager = telemetry_manager or TelemetryManager()

    def start(self) -> dict:
        return {
            "started_at": time.monotonic(),
            "wall_started_at": datetime.now(timezone.utc),
            "hardware": _safe_hardware_snapshot(),
            "process": _safe_process_snapshot(),
            "telemetry": self.telemetry_manager.snapshot("start"),
        }

    def record_response(
        self,
        request: LoadModelRequest,
        response: LoadModelResponse,
        started: dict,
        observed_model_name: str | None = None,
    ) -> RunEvidenceSeed:
        after_hardware = _safe_hardware_snapshot()
        after_process = _safe_process_snapshot()
        telemetry_end = self.telemetry_manager.snapshot("end")
        ended_at = datetime.now(timezone.utc)
        log_capture = self.log_collector(started["wall_started_at"], ended_at)
        process = after_process or started.get("process")
        warnings = _load_warnings(request, response, process)
        if log_capture["error"]:
            warnings.append(log_capture["error"])

        evidence = RunEvidenceSeed(
            id=str(uuid.uuid4()),
            kind="load_attempt",
            model_name=request.model_name,
            requested_model_name=request.model_name,
            observed_model_name=observed_model_name,
            **_identity_fields(self.runtime, request.workflow_profile_id, request.workflow_profile_name),
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
            log_window_started_at=started["wall_started_at"],
            log_window_ended_at=ended_at,
            log_source=log_capture["source"],
            log_entries=log_capture["entries"],
            log_capture_error=log_capture["error"],
            telemetry_samples=[*started["telemetry"].samples, *telemetry_end.samples],
            accelerator_ownership=telemetry_end.accelerator_ownership,
            accelerator_ownership_note=telemetry_end.ownership_note,
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


def _safe_log_snapshot(started_at: datetime, ended_at: datetime) -> dict:
    try:
        response = get_logs_for_window(started_at, ended_at)
    except Exception as exc:
        return {
            "source": "error",
            "entries": [],
            "error": f"Run log capture failed: {exc}",
        }

    error = None
    if response.source == "unavailable":
        error = "Run log capture unavailable; journalctl could not be queried."
    elif response.source == "error":
        error = "Run log capture failed; journalctl returned an error."
    return {
        "source": response.source,
        "entries": response.entries,
        "error": error,
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


def _identity_fields(
    runtime: RuntimeConfig | None,
    workflow_profile_id: str | None,
    workflow_profile_name: str | None,
) -> dict:
    return {
        "runtime_id": runtime.id if runtime else None,
        "runtime_label": runtime.name if runtime else None,
        "runtime_server_url": _normalize_server_url(runtime.url) if runtime else None,
        "workflow_profile_id": workflow_profile_id,
        "workflow_profile_name": workflow_profile_name,
    }


def _normalize_server_url(value: str) -> str:
    """Persist a stable runtime root URL without query strings or fragments."""
    raw = value.strip().rstrip("/")
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlsplit(raw)
    hostname = parsed.hostname or ""
    safe_host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{safe_host}:{port}" if port is not None else safe_host
    path = parsed.path.rstrip("/")
    for suffix in ("/api/v1", "/api", "/v1"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    return urlunsplit((parsed.scheme.lower(), netloc.lower(), path, "", "")).rstrip("/")
