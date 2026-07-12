from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.models.intake import IntakeInspectRequest, IntakeProfileRequest, IntakePullRequest
from app.providers.lemonade import LemonadeProvider
from app.routers.intake import create_intake_profile
from app.services.huggingface_intake import HuggingFaceIntakeService
from app.services.profile_service import ProfileService
from app.services.run_evidence import RunEvidenceStorage


class FakeProvider:
    async def get_pull_variants(self, checkpoint):
        assert checkpoint == "owner/model-GGUF"
        return {
            "suggested_name": "model-GGUF",
            "recipe": "llamacpp",
            "suggested_labels": ["vision"],
            "mmproj_files": ["mmproj-model-f16.gguf"],
            "variants": [
                {
                    "name": "Q4_K_M",
                    "primary_file": "model-Q4_K_M.gguf",
                    "files": ["model-Q4_K_M.gguf"],
                    "sharded": False,
                    "size_bytes": 4 * 1024**3,
                },
                {
                    "name": "Q8_0",
                    "primary_file": "model-Q8_0.gguf",
                    "files": ["model-Q8_0.gguf"],
                    "sharded": False,
                    "size_bytes": 8 * 1024**3,
                },
            ],
        }


class FakeHubClient:
    async def get(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "siblings": [
                    {"rfilename": "model-Q4_K_M.gguf", "lfs": {"size": 4 * 1024**3}},
                    {"rfilename": "onnx/model.onnx", "lfs": {"size": 2 * 1024**3}},
                ]
            },
        )


@pytest.mark.asyncio
async def test_intake_combines_lemonade_variants_hub_formats_and_memory(monkeypatch):
    monkeypatch.setattr(
        "app.services.huggingface_intake.psutil.virtual_memory",
        lambda: SimpleNamespace(total=64 * 1024**3, available=16 * 1024**3),
    )
    report = await HuggingFaceIntakeService(FakeProvider(), FakeHubClient()).inspect("owner/model-GGUF")

    assert report.suggested_model_name == "user.model-GGUF"
    assert report.recommended_variant == "Q4_K_M"
    assert [item.format for item in report.variants] == ["gguf", "gguf", "onnx"]
    assert report.variants[0].estimated_runtime_gb == 4.6
    assert report.variants[0].memory_risk == "low"
    assert next(item for item in report.formats if item.format == "gguf").applicability == "applicable"
    assert next(item for item in report.formats if item.format == "onnx").applicability == "possible"
    assert "Lemonade owns" in report.ownership_note


@pytest.mark.asyncio
async def test_intake_preserves_partial_report_when_hub_metadata_fails(monkeypatch):
    monkeypatch.setattr(
        "app.services.huggingface_intake.psutil.virtual_memory",
        lambda: SimpleNamespace(total=32 * 1024**3, available=12 * 1024**3),
    )

    class FailingClient:
        async def get(self, url):
            request = httpx.Request("GET", url)
            return httpx.Response(503, request=request)

    report = await HuggingFaceIntakeService(FakeProvider(), FailingClient()).inspect("owner/model-GGUF")

    assert report.variants
    assert report.inspection_sources == ["Lemonade /pull/variants"]
    assert any("Hugging Face file metadata was unavailable" in warning for warning in report.warnings)


@pytest.mark.asyncio
async def test_intake_caps_lemonade_variants_to_guided_shortlist(monkeypatch):
    monkeypatch.setattr(
        "app.services.huggingface_intake.psutil.virtual_memory",
        lambda: SimpleNamespace(total=64 * 1024**3, available=32 * 1024**3),
    )

    class ManyVariantsProvider(FakeProvider):
        async def get_pull_variants(self, checkpoint):
            payload = await super().get_pull_variants(checkpoint)
            payload["variants"] = [
                {"name": f"Q{i}", "primary_file": f"model-Q{i}.gguf", "files": [f"model-Q{i}.gguf"], "size_bytes": 1024**3}
                for i in range(8)
            ]
            return payload

    report = await HuggingFaceIntakeService(ManyVariantsProvider(), FakeHubClient()).inspect("owner/model-GGUF")

    assert [item.name for item in report.variants if item.format == "gguf"] == ["Q0", "Q1", "Q2", "Q3", "Q4"]
    assert any("first 5" in warning and "out of 8" in warning for warning in report.warnings)


def test_repo_and_custom_model_names_are_guarded():
    assert IntakeInspectRequest(repo_id="https://huggingface.co/owner/repo").repo_id == "owner/repo"
    with pytest.raises(ValidationError):
        IntakeInspectRequest(repo_id="not-a-repo")
    with pytest.raises(ValidationError):
        IntakePullRequest(model_name="model", checkpoint="owner/repo:Q4", recipe="llamacpp")


@pytest.mark.asyncio
async def test_intake_creates_traceable_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.routers.intake.psutil.virtual_memory",
        lambda: SimpleNamespace(total=64 * 1024**3, available=48 * 1024**3),
    )
    service = ProfileService(
        profiles_dir=tmp_path / "profiles",
        evidence_storage=RunEvidenceStorage(path=tmp_path / "evidence.json"),
    )
    response = await create_intake_profile(
        IntakeProfileRequest(
            repo_id="owner/model-GGUF",
            model_name="user.model-GGUF",
            variant_name="Q4_K_M",
            variant_size_bytes=4 * 1024**3,
            profile_name="Coding Intake",
            intent="Coding Fast",
        ),
        service=service,
    )
    stored = service.get_profile(response.model_name, response.profile_id)

    assert stored is not None
    assert response.model_name == "model-GGUF"
    assert stored.intent == "Coding Fast"
    assert "owner/model-GGUF" in stored.notes
    assert "user.model-GGUF" in stored.notes
    assert "Lemonade owns" in stored.known_caveats[1]
    assert stored.config.ctx_size == 32768


@pytest.mark.asyncio
async def test_intake_search_returns_only_short_candidate_list():
    class SearchClient:
        async def get(self, url):
            assert "search=Gemma" in url
            assert "filter=gguf" in url
            request = httpx.Request("GET", url)
            return httpx.Response(200, request=request, json=[
                {"id": f"owner/gemma-{index}-GGUF", "downloads": 100 - index, "gated": False, "tags": ["gguf"]}
                for index in range(8)
            ])

    results = await HuggingFaceIntakeService(FakeProvider(), SearchClient()).search("Gemma")

    assert len(results) == 5
    assert results[0].repo_id == "owner/gemma-0-GGUF"
    assert results[0].downloads == 100


@pytest.mark.asyncio
async def test_provider_delegates_variant_and_custom_pull_contracts(monkeypatch):
    provider = LemonadeProvider(url="http://lemonade.test", use_settings_admin_key=False)
    calls = []

    async def fake_get(path, **kwargs):
        calls.append(("get", path, None))
        return httpx.Response(200, request=httpx.Request("GET", f"http://lemonade.test{path}"), json={"variants": []})

    async def fake_post(path, body=None, **kwargs):
        calls.append(("post", path, body))
        return httpx.Response(200, request=httpx.Request("POST", f"http://lemonade.test{path}"), json={"status": "success", "message": "ok"})

    monkeypatch.setattr(provider, "_get", fake_get)
    monkeypatch.setattr(provider, "_post", fake_post)
    await provider.get_pull_variants("owner/model GGUF")
    result = await provider.pull_intake_model(IntakePullRequest(
        model_name="user.model-GGUF",
        checkpoint="owner/model-GGUF:Q4_K_M",
        recipe="llamacpp",
        vision=True,
        mmproj="mmproj.gguf",
    ))

    assert calls[0][1] == "/api/v1/pull/variants?checkpoint=owner%2Fmodel%20GGUF"
    assert calls[1][2] == {
        "model_name": "user.model-GGUF",
        "checkpoint": "owner/model-GGUF:Q4_K_M",
        "recipe": "llamacpp",
        "reasoning": False,
        "vision": True,
        "embedding": False,
        "reranking": False,
        "mmproj": "mmproj.gguf",
    }
    assert result.success is True
