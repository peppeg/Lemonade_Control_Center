import pytest

from app.models.schemas import ModelInfo, ModelsListResponse
from app.routers.lemonade import list_models
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
