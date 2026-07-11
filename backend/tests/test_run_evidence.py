import json

import pytest

from app.models.completions import CompletionError, CompletionResult
from app.models.schemas import LoadModelRequest, LoadModelResponse, LogEntry, SmokeTestRequest
from app.models.setup import RuntimeConfig
from app.services.run_evidence import (
    LoadEvidenceRecorder,
    RunEvidenceStorage,
    SmokeTestRunner,
    render_evidence_json,
    render_evidence_markdown,
)


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


def test_run_evidence_storage_filters_and_gets_by_id(tmp_path):
    storage = RunEvidenceStorage(path=tmp_path / "run_evidence.json")
    passed_smoke = _evidence("smoke", "model-a")
    passed_smoke.success = True
    passed_smoke.runtime_id = "runtime-a"
    passed_smoke.workflow_profile_id = "coding"
    failed_load = _evidence("load", "model-a")
    failed_load.kind = "load_attempt"
    storage.add(passed_smoke)
    storage.add(failed_load)

    assert [item.id for item in storage.get_all(kind="smoke_test")] == ["smoke"]
    assert [item.id for item in storage.get_all(success=False)] == ["load"]
    assert [item.id for item in storage.get_all(runtime_id="runtime-a")] == ["smoke"]
    assert [item.id for item in storage.get_all(workflow_profile_id="coding")] == ["smoke"]
    assert storage.get("smoke") == passed_smoke
    assert storage.get("missing") is None


def test_run_evidence_exports_complete_json_and_markdown():
    evidence = _evidence("evidence-1", "qwen-coder")
    evidence.success = True
    evidence.response_text = "pong"
    evidence.reasoning_text = "checked"
    evidence.observed_backend = "vulkan"
    evidence.generation_tps = 12.5
    evidence.log_source = "journalctl"
    evidence.log_entries = [
        LogEntry(
            timestamp="2026-07-10T12:00:00+00:00",
            level="performance",
            message="eval time = 12.5 tokens per second",
            raw="eval time = 12.5 tokens per second",
        )
    ]
    evidence.warnings = ["Token count estimated."]
    evidence.requested_model_name = "qwen-coder:latest"
    evidence.observed_model_name = "qwen-coder"
    evidence.runtime_id = "lemonade-local"
    evidence.runtime_label = "Local Lemonade"
    evidence.runtime_server_url = "http://localhost:13305"
    evidence.workflow_profile_id = "coding"
    evidence.workflow_profile_name = "Coding Fast"

    exported_json = json.loads(render_evidence_json(evidence))
    exported_markdown = render_evidence_markdown(evidence)

    assert exported_json["id"] == "evidence-1"
    assert exported_json["response_text"] == "pong"
    assert exported_json["runtime_id"] == "lemonade-local"
    assert exported_json["workflow_profile_id"] == "coding"
    assert "# LCC Run Evidence" in exported_markdown
    assert "**Backend:** vulkan" in exported_markdown
    assert "Local Lemonade (lemonade-local)" in exported_markdown
    assert "Coding Fast (coding)" in exported_markdown
    assert "qwen-coder:latest" in exported_markdown
    assert "qwen-coder`" in exported_markdown
    assert "pong" in exported_markdown
    assert "## Correlated Logs" in exported_markdown
    assert "[PERFORMANCE] eval time" in exported_markdown
    assert "Token count estimated." in exported_markdown


def test_run_evidence_storage_ignores_invalid_records(tmp_path):
    path = tmp_path / "run_evidence.json"
    path.write_text(
        json.dumps(
            [
                _evidence("valid", "model-a").model_dump(mode="json"),
                {"id": "legacy", "model_name": "model-a"},
                {"id": "missing-required-fields"},
                "not-a-record",
            ]
        ),
        encoding="utf-8",
    )

    results = RunEvidenceStorage(path=path).get_all()

    assert [item.id for item in results] == ["valid", "legacy"]
    assert results[1].completion_endpoint is None
    assert results[1].token_count_source == "unavailable"
    assert results[1].requested_model_name is None
    assert results[1].runtime_id is None
    assert results[1].workflow_profile_id is None


@pytest.mark.asyncio
async def test_smoke_test_runner_stores_process_and_memory_evidence(tmp_path, monkeypatch):
    storage = RunEvidenceStorage(path=tmp_path / "run_evidence.json")
    completion_runner = FakeCompletionRunner()
    logs = FakeLogCollector()
    runner = SmokeTestRunner(
        completion_runner=completion_runner,
        storage=storage,
        log_collector=logs,
        runtime=_runtime(),
    )

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

    response = await runner.run(
        SmokeTestRequest(
            model_name="qwen-coder",
            max_tokens=128,
            temperature=0.25,
            app_timeout_seconds=240,
            stop_sequences=["DONE"],
            workflow_profile_id="coding",
            workflow_profile_name="Coding Fast",
        )
        ,
        observed_model_name="qwen-coder-canonical",
    )

    assert response.success is True
    assert response.evidence.model_name == "qwen-coder"
    assert response.evidence.requested_model_name == "qwen-coder"
    assert response.evidence.observed_model_name == "qwen-coder-canonical"
    assert response.evidence.runtime_id == "lemonade-local"
    assert response.evidence.runtime_label == "Local Lemonade"
    assert response.evidence.runtime_server_url == "http://localhost:13305"
    assert response.evidence.workflow_profile_id == "coding"
    assert response.evidence.workflow_profile_name == "Coding Fast"
    assert response.evidence.response_text == "LCC_SMOKE_OK"
    assert response.evidence.reasoning_text == "internal reasoning"
    assert response.evidence.completion_endpoint == "/v1/chat/completions"
    assert response.evidence.token_count_source == "api"
    assert response.evidence.observed_pid == 1234
    assert response.evidence.observed_backend == "vulkan"
    assert response.evidence.observed_ctx_size == 65536
    assert response.evidence.ram_used_before_gb == 40.0
    assert response.evidence.ram_used_after_gb == 41.5
    assert response.evidence.request_max_tokens == 128
    assert response.evidence.request_temperature == 0.25
    assert response.evidence.request_timeout_seconds == 240
    assert response.evidence.request_stop_sequences == ["DONE"]
    assert response.evidence.log_source == "journalctl"
    assert response.evidence.log_entries[0].message == "request completed"
    assert response.evidence.log_window_started_at == logs.started_at
    assert response.evidence.log_window_ended_at == logs.ended_at
    assert completion_runner.last_request.max_tokens == 128
    assert completion_runner.last_request.temperature == 0.25
    assert completion_runner.last_request.timeout_seconds == 240
    assert completion_runner.last_request.stop_sequences == ["DONE"]
    assert storage.get_all()[0].id == response.evidence.id


@pytest.mark.asyncio
async def test_smoke_test_runner_stores_structured_completion_failure(tmp_path, monkeypatch):
    storage = RunEvidenceStorage(path=tmp_path / "run_evidence.json")
    completion_runner = FailingCompletionRunner()
    runner = SmokeTestRunner(
        completion_runner=completion_runner,
        storage=storage,
        log_collector=FakeLogCollector(source="unavailable"),
    )
    monkeypatch.setattr("app.services.run_evidence._safe_hardware_snapshot", lambda: None)
    monkeypatch.setattr("app.services.run_evidence._safe_process_snapshot", lambda: None)

    response = await runner.run(SmokeTestRequest(model_name="qwen-coder"))

    assert response.success is False
    assert response.evidence.error == "Completion request timed out."
    assert response.evidence.completion_error_kind == "timeout"
    assert response.evidence.response_text == "partial"
    assert "Smoke request failed" in response.evidence.warnings[0]
    assert response.evidence.log_capture_error is not None


def test_load_evidence_recorder_stores_requested_and_observed_load_state(tmp_path, monkeypatch):
    storage = RunEvidenceStorage(path=tmp_path / "run_evidence.json")
    recorder = LoadEvidenceRecorder(storage=storage, log_collector=FakeLogCollector(), runtime=_runtime())

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
            workflow_profile_id="review",
            workflow_profile_name="Review Heavy",
        ),
        LoadModelResponse(success=True, message="loaded"),
        started,
        observed_model_name="qwen-coder-canonical",
    )

    assert evidence.kind == "load_attempt"
    assert evidence.success is True
    assert evidence.load_message == "loaded"
    assert evidence.requested_model_name == "qwen-coder"
    assert evidence.observed_model_name == "qwen-coder-canonical"
    assert evidence.runtime_id == "lemonade-local"
    assert evidence.runtime_server_url == "http://localhost:13305"
    assert evidence.workflow_profile_id == "review"
    assert evidence.workflow_profile_name == "Review Heavy"
    assert evidence.requested_backend == "rocm"
    assert evidence.requested_ctx_size == 65536
    assert evidence.requested_llamacpp_args == "--flash-attn on"
    assert evidence.observed_pid == 4321
    assert evidence.observed_backend == "vulkan"
    assert evidence.observed_ctx_size == 32768
    assert evidence.ram_used_before_gb == 50.0
    assert evidence.ram_used_after_gb == 72.0
    assert evidence.log_source == "journalctl"
    assert evidence.log_entries[0].message == "request completed"
    assert "Requested backend rocm, observed vulkan." in evidence.warnings
    assert "Requested ctx 65536, observed 32768." in evidence.warnings
    assert storage.get_all()[0].id == evidence.id


class FakeCompletionRunner:
    def __init__(self):
        self.last_request = None

    async def run(self, request):
        self.last_request = request
        return CompletionResult(
            model=request.model,
            reasoning_text="internal reasoning",
            input_tokens=6,
            output_tokens=3,
            token_count_source="api",
            prompt_eval_tps=100.0,
            generation_tps=20.0,
            ttft_seconds=0.2,
            total_seconds=0.4,
            finish_reason="stop",
            finish_confidence="confirmed",
            response_text="LCC_SMOKE_OK",
            endpoint="/v1/chat/completions",
        )


class FailingCompletionRunner:
    async def run(self, request):
        return CompletionResult(
            model=request.model,
            response_text="partial",
            error=CompletionError(kind="timeout", message="Completion request timed out."),
        )


class FakeHardwareSnapshots:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def __call__(self):
        return self.snapshots.pop(0)


class FakeLogCollector:
    def __init__(self, source="journalctl"):
        self.source = source
        self.started_at = None
        self.ended_at = None

    def __call__(self, started_at, ended_at):
        self.started_at = started_at
        self.ended_at = ended_at
        error = None if self.source == "journalctl" else "Run log capture unavailable."
        entries = [LogEntry(message="request completed", raw="request completed")] if not error else []
        return {"source": self.source, "entries": entries, "error": error}


def _evidence(id_: str, model_name: str):
    from app.models.schemas import RunEvidenceSeed

    return RunEvidenceSeed(
        id=id_,
        model_name=model_name,
        prompt="ping",
    )


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(
        id="lemonade-local",
        type="lemonade",
        name="Local Lemonade",
        url="HTTP://operator:secret@LOCALHOST:13305/api/v1/?token=discarded",
        is_active=True,
    )
