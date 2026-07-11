"""
Router that proxies all Lemonade API calls through the LemonadeProvider.

Every endpoint is capability-driven: if the underlying Lemonade endpoint
isn't available, the provider raises a clean 501 error.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.dependencies import get_active_runtime_config, get_completion_runner, get_provider
from app.models.setup import RuntimeConfig
from app.providers.lemonade import LemonadeProvider
from app.models.backend_readiness import BackendReadinessResponse
from app.models.schemas import (
    LemonadeHealthResponse,
    LemonadeStatsResponse,
    ModelsListResponse,
    RunningModelsResponse,
    ModelShowResponse,
    LoadModelRequest,
    LoadModelResponse,
    RunEvidenceSeed,
    RunEvidenceListResponse,
    PullModelRequest,
    PullModelResponse,
    SmokeTestRequest,
    SmokeTestResponse,
    UnloadModelRequest,
    LemonadeConfigResponse,
    LemonadeSavedOptionsResponse,
    ConfigUpdateRequest,
)
from app.services.lemonade_options import read_saved_options
from app.services.backend_readiness import collect_backend_readiness
from app.services.completion_runner import CompletionRunner
from app.services.run_evidence import (
    LoadEvidenceRecorder,
    RunEvidenceStorage,
    SmokeTestRunner,
    render_evidence_json,
    render_evidence_markdown,
)

router = APIRouter(prefix="/api/lemonade", tags=["lemonade"])


@router.get("/health", response_model=LemonadeHealthResponse)
async def lemonade_health(provider: LemonadeProvider = Depends(get_provider)):
    """Get Lemonade server health status."""
    return await provider.get_health()


@router.get("/stats", response_model=LemonadeStatsResponse)
async def lemonade_stats(provider: LemonadeProvider = Depends(get_provider)):
    """Get performance stats from last Lemonade request."""
    return await provider.get_stats()


@router.get("/system-info")
async def lemonade_system_info(provider: LemonadeProvider = Depends(get_provider)):
    """Get Lemonade system/device info."""
    return await provider.get_system_info()


@router.get("/backend-readiness", response_model=BackendReadinessResponse)
async def backend_readiness(provider: LemonadeProvider = Depends(get_provider)):
    """Return normalized authoritative backend state from Lemonade system-info."""
    return await collect_backend_readiness(provider)


@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    catalog: bool = Query(default=False),
    provider: LemonadeProvider = Depends(get_provider),
):
    """List downloaded models, optionally including the Lemonade catalog."""
    return await provider.list_models(include_catalog=catalog)


@router.get("/running", response_model=RunningModelsResponse)
async def running_models(provider: LemonadeProvider = Depends(get_provider)):
    """List currently loaded/running models."""
    return await provider.get_running_models()


@router.get("/saved-options", response_model=LemonadeSavedOptionsResponse)
async def saved_options(model_name: str | None = None):
    """Read Lemonade's official saved per-model load options."""
    return read_saved_options(model_name)


@router.get("/models/{model_name}", response_model=ModelShowResponse)
async def show_model(
    model_name: str,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Get detailed info about a specific model."""
    return await provider.show_model(model_name)


@router.post("/load", response_model=LoadModelResponse)
async def load_model(
    request: LoadModelRequest,
    provider: LemonadeProvider = Depends(get_provider),
    runtime: RuntimeConfig | None = Depends(get_active_runtime_config),
):
    """Load a model into memory with optional configuration."""
    recorder = LoadEvidenceRecorder(runtime=runtime)
    started = recorder.start()
    try:
        response = await provider.load_model(request)
    except Exception as exc:
        recorder.record_exception(request, exc, started)
        raise
    response.evidence = recorder.record_response(
        request,
        response,
        started,
        observed_model_name=await _observed_model_name(provider),
    )
    return response


@router.post("/smoke-test", response_model=SmokeTestResponse)
async def smoke_test(
    request: SmokeTestRequest,
    completion_runner: CompletionRunner = Depends(get_completion_runner),
    provider: LemonadeProvider = Depends(get_provider),
    runtime: RuntimeConfig | None = Depends(get_active_runtime_config),
):
    """Run a small post-load request and save a local run evidence seed."""
    return await SmokeTestRunner(
        completion_runner=completion_runner,
        runtime=runtime,
    ).run(request, observed_model_name=await _observed_model_name(provider))


@router.get("/run-evidence", response_model=RunEvidenceListResponse)
async def run_evidence(
    model_name: str | None = None,
    kind: Literal["smoke_test", "load_attempt"] | None = None,
    success: bool | None = None,
    runtime_id: str | None = None,
    workflow_profile_id: str | None = None,
):
    """Return local run evidence seeds."""
    results = RunEvidenceStorage().get_all(
        model_name=model_name,
        kind=kind,
        success=success,
        runtime_id=runtime_id,
        workflow_profile_id=workflow_profile_id,
    )
    return RunEvidenceListResponse(results=results, total=len(results))


@router.get("/run-evidence/{evidence_id}", response_model=RunEvidenceSeed)
async def run_evidence_detail(evidence_id: str):
    """Return one complete local evidence record."""
    evidence = RunEvidenceStorage().get(evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Run evidence not found.")
    return evidence


@router.get("/run-evidence/{evidence_id}/export")
async def export_run_evidence(
    evidence_id: str,
    format: Literal["json", "markdown"] = "json",
):
    """Download one complete evidence record as JSON or Markdown."""
    evidence = RunEvidenceStorage().get(evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Run evidence not found.")

    extension = "json" if format == "json" else "md"
    filename_id = "".join(character for character in evidence.id if character.isalnum() or character in "-_")
    filename_id = filename_id or "record"
    content = (
        render_evidence_json(evidence)
        if format == "json"
        else render_evidence_markdown(evidence)
    )
    media_type = "application/json" if format == "json" else "text/markdown; charset=utf-8"
    return PlainTextResponse(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="lcc-run-evidence-{filename_id}.{extension}"'},
    )


async def _observed_model_name(provider: LemonadeProvider) -> str | None:
    """Read the canonical loaded model name when Lemonade exposes it."""
    try:
        running = await provider.get_running_models()
    except Exception:
        return None
    return running.models[0].name if running.models else None


@router.post("/pull", response_model=PullModelResponse)
async def pull_model(
    request: PullModelRequest,
    provider: LemonadeProvider = Depends(get_provider),
):
    """Download/install a registered Lemonade model."""
    return await provider.pull_model(request)


@router.post("/unload")
async def unload_model(
    request: UnloadModelRequest,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Unload a model from memory."""
    return await provider.unload_model(request.model_name)


@router.delete("/models/{model_name}")
async def delete_model(
    model_name: str,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Delete a model from disk. Requires ENABLE_DELETE=true."""
    await provider.delete_model(model_name)
    return {"success": True, "message": f"Model '{model_name}' deleted."}


@router.get("/config", response_model=LemonadeConfigResponse)
async def get_config(provider: LemonadeProvider = Depends(get_provider)):
    """Get current Lemonade config. Requires admin API key."""
    return await provider.get_config()


@router.post("/config")
async def update_config(
    request: ConfigUpdateRequest,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Update Lemonade config. Requires admin API key."""
    return await provider.set_config(request)
