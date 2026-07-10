"""Bench Lab endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.dependencies import get_completion_runner
from app.services.bench.models import BenchPrompt, BenchRunRequest
from app.services.bench.runner import BenchRunner
from app.services.bench.storage import BenchStorage
from app.services.bench.suites import SUITES
from app.services.completion_runner import CompletionRunner

router = APIRouter(prefix="/api/bench", tags=["bench"])
storage = BenchStorage()


@router.get("/suites")
async def list_suites():
    return {"suites": [suite.model_dump(mode="json") for suite in SUITES.values()]}


@router.post("/run")
async def run_bench(
    request: BenchRunRequest,
    completion_runner: CompletionRunner = Depends(get_completion_runner),
):
    runner = BenchRunner(completion_runner)
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


@router.post("/clear")
async def clear_results():
    storage.clear()
    return {"cleared": True}
