import json

import pytest

from app.models.schemas import LoadModelRequest, LoadModelResponse, SmokeTestRequest
from app.services.bench.models import BenchResult
from app.services.run_evidence import LoadEvidenceRecorder, RunEvidenceStorage, SmokeTestRunner


def test_run_evidence_storage_filters_and_keeps_newest(tmp_path):
    storage = RunEvidenceStorage(path=tmp_path / "run_evidence.json", max_results=2)

    first = _evidence("first", "model-a")
    second = _evidence("second", "model-b")
    third = _evidence("third", "model-a")

    storage.add(first)
    storage.add(second)
    storage.add(third)

    all_results = storage.get_all()
    assert [item.id for item in all_results] == ["third", "second"]
    assert [item.id for item in storage.get_all(model_name="model-a")] == ["third"]


def test_run_evidence_storage_ignores_invalid_records(tmp_path):
    path = tmp_path / "run_evidence.json"
    path.write_text(
        json.dumps(
            [
                _evidence("valid", "model-a").model_dump(mode="json"),
                {"id": "missing-required-fields"},
                "not-a-record",
            ]
        ),
        encoding="utf-8",
    )

    results = RunEvidenceStorage(path=path).get_all()

    assert [item.id for item in results] == ["valid"]


@pytest.mark.asyncio
async def test_smoke_test_runner_stores_process_and_memory_evidence(tmp_path, monkeypatch):
    storage = RunEvidenceStorage(path=tmp_path / "run_evidence.json")
    runner = SmokeTestRunner(bench_runner=FakeBenchRunner(), storage=storage)

    monkeypatch.setattr(
        "app.services.run_evidence._safe_hardware_snapshot",
        FakeHardwareSnapshots(
            [
                {"ram_used_gb": 40.0, "swap_used_gb": 0.0},
                {"ram_used_gb": 41.5, "swap_used_gb": 0.0},
            ]
        ),
    )
    monkeypatch.setattr(
        "app.services.run_evidence._safe_process_snapshot",
        lambda: {"pid": 1234, "rss_gb": 38.2, "backend": "vulkan", "ctx_size": 65536},
    )

    response = await runner.run(SmokeTestRequest(model_name="qwen-coder"))

    assert response.success is True
    assert response.evidence.model_name == "qwen-coder"
    assert response.evidence.response_text == "LCC_SMOKE_OK"
    assert response.evidence.observed_pid == 1234
    assert response.evidence.observed_backend == "vulkan"
    assert response.evidence.observed_ctx_size == 65536
    assert response.evidence.ram_used_before_gb == 40.0
    assert response.evidence.ram_used_after_gb == 41.5
    assert storage.get_all()[0].id == response.evidence.id


def test_load_evidence_recorder_stores_requested_and_observed_load_state(tmp_path, monkeypatch):
    storage = RunEvidenceStorage(path=tmp_path / "run_evidence.json")
    recorder = LoadEvidenceRecorder(storage=storage)

    monkeypatch.setattr(
        "app.services.run_evidence._safe_hardware_snapshot",
        FakeHardwareSnapshots(
            [
                {"ram_used_gb": 50.0, "swap_used_gb": 0.0},
                {"ram_used_gb": 72.0, "swap_used_gb": 0.0},
            ]
        ),
    )
    monkeypatch.setattr(
        "app.services.run_evidence._safe_process_snapshot",
        lambda: {"pid": 4321, "rss_gb": 60.0, "backend": "vulkan", "ctx_size": 32768},
    )

    started = recorder.start()
    evidence = recorder.record_response(
        LoadModelRequest(
            model_name="qwen-coder",
            ctx_size=65536,
            llamacpp_backend="rocm",
            llamacpp_args="--flash-attn on",
            merge_args=True,
            save_options=True,
        ),
        LoadModelResponse(success=True, message="loaded"),
        started,
    )

    assert evidence.kind == "load_attempt"
    assert evidence.success is True
    assert evidence.load_message == "loaded"
    assert evidence.requested_backend == "rocm"
    assert evidence.requested_ctx_size == 65536
    assert evidence.requested_llamacpp_args == "--flash-attn on"
    assert evidence.observed_pid == 4321
    assert evidence.observed_backend == "vulkan"
    assert evidence.observed_ctx_size == 32768
    assert evidence.ram_used_before_gb == 50.0
    assert evidence.ram_used_after_gb == 72.0
    assert "Requested backend rocm, observed vulkan." in evidence.warnings
    assert "Requested ctx 65536, observed 32768." in evidence.warnings
    assert storage.get_all()[0].id == evidence.id


class FakeBenchRunner:
    async def run_prompt(self, prompt, model):
        return BenchResult(
            prompt_id=prompt.id,
            prompt_name=prompt.name,
            model=model,
            input_tokens=6,
            output_tokens=3,
            prompt_eval_tps=100.0,
            generation_tps=20.0,
            ttft_seconds=0.2,
            total_seconds=0.4,
            finish_reason="stop",
            finish_confidence="confirmed",
            response_preview="LCC_SMOKE_OK",
            response_full="LCC_SMOKE_OK",
        )


class FakeHardwareSnapshots:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def __call__(self):
        return self.snapshots.pop(0)


def _evidence(id_: str, model_name: str):
    from app.models.schemas import RunEvidenceSeed

    return RunEvidenceSeed(
        id=id_,
        model_name=model_name,
        prompt="ping",
    )
