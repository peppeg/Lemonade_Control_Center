"""Bench Lab endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.dependencies import get_active_runtime_config, get_completion_runner, get_provider
from app.models.setup import RuntimeConfig
from app.providers.lemonade import LemonadeProvider
from app.services.bench.models import BenchAnnotationRequest, BenchPrompt, BenchRunRequest
from app.services.bench.runner import BenchRunner
from app.services.bench.storage import BenchStorage
from app.services.bench.suites import SUITES
from app.services.completion_runner import CompletionRunner
from app.services.run_evidence import _normalize_server_url

router = APIRouter(prefix="/api/bench", tags=["bench"])
storage = BenchStorage()


@router.get("/suites")
async def list_suites():
    return {"suites": [suite.model_dump(mode="json") for suite in SUITES.values()]}


@router.post("/run")
async def run_bench(
    request: BenchRunRequest,
    completion_runner: CompletionRunner = Depends(get_completion_runner),
    provider: LemonadeProvider = Depends(get_provider),
    runtime: RuntimeConfig | None = Depends(get_active_runtime_config),
):
    identity = await _bench_identity(request, provider, runtime)
    observed_model = identity.get("observed_model_name")
    if observed_model and observed_model != request.model:
        raise HTTPException(
            409,
            f"Bench requested model '{request.model}', but Lemonade reports '{observed_model}' as loaded.",
        )
    if request.suite_id and not request.workflow_profile_id:
        raise HTTPException(400, "Apply a workflow profile to the selected model before running a suite.")
    runner = BenchRunner(completion_runner, identity=identity)
    if request.suite_id:
        if request.suite_id not in SUITES:
            raise HTTPException(404, f"Suite '{request.suite_id}' not found")
        result = await runner.run_suite(request.suite_id, request.model)
        storage.add_suite_result(result)
        return result.model_dump(mode="json")
    if request.prompt:
        prompt = BenchPrompt(
            id="quick",
            name="Quick Test",
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        result = await runner.run_prompt(prompt, request.model)
        storage.add_quick_result(result)
        return result.model_dump(mode="json")
    raise HTTPException(400, "Provide either prompt or suite_id.")


@router.get("/results")
async def get_results(model: str | None = None, suite: str | None = None):
    return {"results": storage.get_all(model=model, suite=suite)}


@router.get("/results/csv")
async def export_csv():
    return PlainTextResponse(
        storage.export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bench-results.csv"},
    )


@router.get("/results/markdown")
async def export_markdown():
    return PlainTextResponse(
        storage.export_markdown(),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=bench-results.md"},
    )


@router.get("/results/json")
async def export_json():
    return PlainTextResponse(
        storage.export_json(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=bench-results.json"},
    )


@router.patch("/results/{result_id}")
async def annotate_result(result_id: str, request: BenchAnnotationRequest):
    result = storage.annotate(result_id, request)
    if result is None:
        raise HTTPException(404, "Bench result not found.")
    return result


@router.get("/compare")
async def compare_results(result_ids: str):
    try:
        return storage.compare(_result_ids(result_ids)).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/compare/markdown")
async def export_comparison(result_ids: str):
    try:
        content = storage.export_comparison_markdown(_result_ids(result_ids))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return PlainTextResponse(
        content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=bench-comparison.md"},
    )


@router.post("/clear")
async def clear_results():
    storage.clear()
    return {"cleared": True}


async def _bench_identity(
    request: BenchRunRequest,
    provider: LemonadeProvider,
    runtime: RuntimeConfig | None,
) -> dict:
    observed_model_name = None
    try:
        running = await provider.get_running_models()
        observed_model_name = running.models[0].name if running.models else None
    except Exception:
        pass
    return {
        "observed_model_name": observed_model_name,
        "runtime_id": runtime.id if runtime else None,
        "runtime_label": runtime.name if runtime else None,
        "runtime_server_url": _normalize_server_url(runtime.url) if runtime else None,
        "workflow_profile_id": request.workflow_profile_id,
        "workflow_profile_name": request.workflow_profile_name,
    }


def _result_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
