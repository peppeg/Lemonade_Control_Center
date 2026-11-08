import httpx
import pytest

from app.providers.lemonade import LemonadeProvider
from app.routers.lemonade import saved_options


def _provider_returning(monkeypatch, response: httpx.Response) -> LemonadeProvider:
    provider = LemonadeProvider("http://lemonade.test", use_settings_admin_key=False)

    async def fake_get(path, **kwargs):
        assert path == "/api/v1/models"
        return response

    monkeypatch.setattr(provider, "_get", fake_get)
    return provider


@pytest.mark.asyncio
async def test_recipe_options_come_from_models_api(monkeypatch):
    provider = _provider_returning(monkeypatch, httpx.Response(200, json={"data": [
        {"id": "Qwen3.5-9B-GGUF", "recipe_options": {"llamacpp_args": "--reasoning off"}},
        {"id": "Gemma-4-31B-it-GGUF", "recipe_options": {}},
    ]}))

    assert await provider.get_recipe_options() == {"Qwen3.5-9B-GGUF": {"llamacpp_args": "--reasoning off"}}


@pytest.mark.asyncio
async def test_recipe_options_are_unknown_on_older_lemonade(monkeypatch):
    provider = _provider_returning(monkeypatch, httpx.Response(200, json={"data": [{"id": "Qwen3.5-9B-GGUF"}]}))

    assert await provider.get_recipe_options() is None


class FakeProvider:
    base_url = "http://lemonade.test"

    def __init__(self, options):
        self.options = options

    async def get_recipe_options(self):
        return self.options


@pytest.mark.asyncio
async def test_saved_options_prefers_api_and_selects_model():
    result = await saved_options(
        model_name="Qwen3.5-9B-GGUF",
        provider=FakeProvider({"Qwen3.5-9B-GGUF": {"ctx_size": 32768}}),
    )

    assert result.available is True
    assert result.source == "api"
    assert result.path == "http://lemonade.test/api/v1/models"
    assert result.selected_key == "Qwen3.5-9B-GGUF"
    assert result.selected_options == {"ctx_size": 32768}


@pytest.mark.asyncio
async def test_saved_options_falls_back_to_recipe_options_file(monkeypatch, tmp_path):
    path = tmp_path / "recipe_options.json"
    path.write_text('{"builtin.Qwen3.5-9B-GGUF": {"ctx_size": 8192}}', encoding="utf-8")
    monkeypatch.setattr("app.services.lemonade_options.settings.lemonade_recipe_options_file", str(path))

    result = await saved_options(model_name="Qwen3.5-9B-GGUF", provider=FakeProvider(None))

    assert result.source == "file"
    assert result.selected_key == "builtin.Qwen3.5-9B-GGUF"
    assert result.selected_options == {"ctx_size": 8192}
