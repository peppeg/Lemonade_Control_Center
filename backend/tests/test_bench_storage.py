import json

import pytest
from fastapi import HTTPException

from app.services.bench.models import BenchAnnotationRequest, BenchResult, SuiteResult
from app.services.bench.storage import BenchStorage
from app.routers import bench as bench_router
from app.models.setup import RuntimeConfig
from app.services.bench.models import BenchRunRequest


def _suite(id_: str, model: str, profile_id: str, tps: float) -> SuiteResult:
    prompt = BenchResult(
        prompt_id="agent_patch",
        prompt_name="Scoped Patch",
        prompt="Make a scoped patch.",
        model=model,
        requested_model_name=model,
        observed_model_name=model,
        runtime_id="runtime-a",
        runtime_label="Local Lemonade",
        workflow_profile_id=profile_id,
        workflow_profile_name=profile_id.title(),
        response_full="complete response",
        reasoning_text="reasoning",
        generation_tps=tps,
        observed_backend="vulkan",
        observed_ctx_size=32768,
        ram_used_before_gb=20,
        ram_used_after_gb=24,
    )
    return SuiteResult(
        id=id_,
        suite_id="coding_agent",
        suite_name="Coding Agent Workflows",
        model=model,
        requested_model_name=model,
        observed_model_name=model,
        runtime_id="runtime-a",
        runtime_label="Local Lemonade",
        workflow_profile_id=profile_id,
        workflow_profile_name=profile_id.title(),
        results=[prompt],
        avg_gen_tps=tps,
        avg_ttft=0.2,
        total_tokens=100,
        total_seconds=2,
        truncated_count=0,
        error_count=0,
    )


def test_bench_storage_preserves_evidence_and_manual_assessment(tmp_path):
    storage = BenchStorage(path=tmp_path / "bench.json")
    storage.add_suite_result(_suite("run-a", "model-a", "coding-fast", 12.5))

    updated = storage.annotate(
        "run-a",
        BenchAnnotationRequest(manual_quality_score=4, manual_notes="Good patch; terse review."),
    )

    assert updated is not None
    assert updated["manual_quality_score"] == 4
    assert updated["manual_notes"] == "Good patch; terse review."
    stored = storage.get_all()[0]
    assert stored["results"][0]["response_full"] == "complete response"
    assert stored["results"][0]["reasoning_text"] == "reasoning"
    assert stored["results"][0]["observed_backend"] == "vulkan"
    assert stored["results"][0]["ram_used_after_gb"] == 24

    reloaded = BenchStorage(path=tmp_path / "bench.json").get_all()[0]
    assert reloaded["manual_quality_score"] == 4


def test_bench_storage_compares_same_suite_and_exports_readable_report(tmp_path):
    storage = BenchStorage(path=tmp_path / "bench.json")
    storage.add_suite_result(_suite("run-a", "model-a", "coding-fast", 12.5))
    storage.add_suite_result(_suite("run-b", "model-b", "review-heavy", 8.0))
    storage.annotate("run-a", BenchAnnotationRequest(manual_quality_score=5, manual_notes="Best result."))

    comparison = storage.compare(["run-a", "run-b"])
    report = storage.export_comparison_markdown(["run-a", "run-b"])

    assert comparison.suite_id == "coding_agent"
    assert {result.workflow_profile_id for result in comparison.results} == {"coding-fast", "review-heavy"}
    assert "# Bench Comparison: Coding Agent Workflows" in report
    assert "model-a | Coding-Fast" in report
    assert "Best result." in report


def test_bench_storage_rejects_incompatible_or_missing_comparisons(tmp_path):
    storage = BenchStorage(path=tmp_path / "bench.json")
    storage.add_suite_result(_suite("run-a", "model-a", "coding-fast", 12.5))
    other = _suite("run-b", "model-b", "review-heavy", 8.0)
    other.suite_id = "other-suite"
    other.suite_name = "Other Suite"
    storage.add_suite_result(other)

    try:
        storage.compare(["run-a"])
        raise AssertionError("Expected missing comparison to fail")
    except ValueError as exc:
        assert "at least two" in str(exc)

    try:
        storage.compare(["run-a", "run-b"])
        raise AssertionError("Expected incompatible comparison to fail")
    except ValueError as exc:
        assert "same suite" in str(exc)

    invalid = _suite("run-c", "model-c", "invalid", 7.0)
    invalid.workflow_profile_id = None
    storage.add_suite_result(invalid)
    try:
        storage.compare(["run-a", "run-c"])
        raise AssertionError("Expected missing profile identity to fail")
    except ValueError as exc:
        assert "workflow profile" in str(exc)


def test_bench_storage_migrates_legacy_results_with_ids(tmp_path):
    path = tmp_path / "bench.json"
    path.write_text(
        json.dumps({"suites": [{"suite_id": "legacy", "results": [{}]}], "quick": [{"suite_id": "quick"}]}),
        encoding="utf-8",
    )

    results = BenchStorage(path=path).get_all()
    persisted = json.loads(path.read_text(encoding="utf-8"))

    assert all(result.get("id") for result in results)
    assert persisted["suites"][0]["results"][0]["id"]


@pytest.mark.asyncio
async def test_bench_annotation_and_comparison_endpoints(tmp_path, monkeypatch):
    storage = BenchStorage(path=tmp_path / "bench.json")
    storage.add_suite_result(_suite("run-a", "model-a", "coding-fast", 12.5))
    storage.add_suite_result(_suite("run-b", "model-b", "review-heavy", 8.0))
    monkeypatch.setattr(bench_router, "storage", storage)

    annotated = await bench_router.annotate_result(
        "run-a",
        BenchAnnotationRequest(manual_quality_score=5, manual_notes="Strong result."),
    )
    comparison = await bench_router.compare_results("run-a,run-b")
    report = await bench_router.export_comparison("run-a,run-b")

    assert annotated["manual_quality_score"] == 5
    assert comparison["suite_id"] == "coding_agent"
    assert b"# Bench Comparison" in report.body

    with pytest.raises(HTTPException) as exc_info:
        await bench_router.annotate_result("missing", BenchAnnotationRequest())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_bench_run_rejects_requested_observed_model_mismatch(monkeypatch):
    class Provider:
        async def get_running_models(self):
            class Model:
                name = "observed-model"

            class Running:
                models = [Model()]

            return Running()

    with pytest.raises(HTTPException) as exc_info:
        await bench_router.run_bench(
            BenchRunRequest(model="requested-model", suite_id="coding_agent", workflow_profile_id="safe"),
            completion_runner=object(),
            provider=Provider(),
            runtime=RuntimeConfig(id="runtime-a", type="lemonade", name="Local", url="http://localhost:13305"),
        )

    assert exc_info.value.status_code == 409
    assert "observed-model" in exc_info.value.detail
