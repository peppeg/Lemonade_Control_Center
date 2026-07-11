import pytest
from fastapi import HTTPException

from app.models.schemas import ModelInfo, ModelsListResponse, RunEvidenceSeed
from app.dependencies import get_completion_runner
from app.routers.lemonade import export_run_evidence, list_models, run_evidence, run_evidence_detail
from app.services.security import security_status


class FakeProvider:
    async def list_models(self, include_catalog: bool = False) -> ModelsListResponse:
        return ModelsListResponse(
            models=[
                ModelInfo(
                    name="Qwen-Test-GGUF",
                    size=24 * 1024**3,
                    downloaded=True,
                )
            ],
            source="merged_catalog" if include_catalog else "ollama_tags",
        )


@pytest.mark.asyncio
async def test_models_endpoint_uses_provider_and_catalog_flag(monkeypatch):
    result = await list_models(catalog=True, provider=FakeProvider())

    assert result.source == "merged_catalog"
    assert result.models[0].name == "Qwen-Test-GGUF"
    assert result.models[0].size == 24 * 1024**3


def test_security_status_for_remote_clients(monkeypatch):
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", None)

    assert security_status("192.168.1.20") == {
        "auth_required": True,
        "authenticated": False,
        "key_configured": False,
        "lan_client": True,
        "client_host": "192.168.1.20",
        "blocked": True,
        "mode": "lan",
    }


def test_completion_runner_uses_active_provider_url():
    class Provider:
        base_url = "http://active-runtime.test:13305"

    runner = get_completion_runner(provider=Provider())

    assert runner.base_url == "http://active-runtime.test:13305"


@pytest.mark.asyncio
async def test_run_evidence_endpoints_filter_and_return_detail(monkeypatch):
    stored = RunEvidenceSeed(id="run-1", model_name="qwen-test", success=True)

    class FakeStorage:
        def get_all(self, **filters):
            assert filters == {
                "model_name": "qwen-test",
                "kind": "smoke_test",
                "success": True,
                "runtime_id": "runtime-a",
                "workflow_profile_id": "coding",
            }
            return [stored]

        def get(self, evidence_id):
            return stored if evidence_id == stored.id else None

    monkeypatch.setattr("app.routers.lemonade.RunEvidenceStorage", FakeStorage)

    listing = await run_evidence(
        model_name="qwen-test",
        kind="smoke_test",
        success=True,
        runtime_id="runtime-a",
        workflow_profile_id="coding",
    )
    detail = await run_evidence_detail("run-1")

    assert listing.total == 1
    assert listing.results == [stored]
    assert detail == stored

    with pytest.raises(HTTPException) as exc_info:
        await run_evidence_detail("missing")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_run_evidence_export_sets_safe_attachment_name(monkeypatch):
    stored = RunEvidenceSeed(id="../run-1", model_name="qwen-test", response_text="ok")

    class FakeStorage:
        def get(self, evidence_id):
            return stored

    monkeypatch.setattr("app.routers.lemonade.RunEvidenceStorage", FakeStorage)

    response = await export_run_evidence("../run-1", format="markdown")

    assert response.media_type == "text/markdown; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="lcc-run-evidence-run-1.md"'
    assert b"# LCC Run Evidence" in response.body
