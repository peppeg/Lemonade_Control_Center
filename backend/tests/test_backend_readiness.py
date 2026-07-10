import pytest

from app.routers.lemonade import backend_readiness
from app.services.backend_readiness import normalize_backend_readiness


SYSTEM_INFO = {
    "recipes": {
        "llamacpp": {
            "web_display_name": "Llama.cpp GPU",
            "experimental": False,
            "backends": {
                "vulkan": {
                    "state": "installed",
                    "version": "b9747",
                    "devices": ["amd_gpu", "cpu"],
                },
                "rocm": {
                    "state": "update_required",
                    "version": "b9174",
                    "message": "Backend update is required before use.",
                    "action": "lemonade backends install llamacpp:rocm",
                    "devices": ["amd_gpu"],
                    "release_url": "https://example.test/llama.cpp/b9752",
                    "download_filename": "llama-rocm.tar.gz",
                },
                "cpu": {
                    "state": "installable",
                    "message": "Backend is supported but not installed.",
                    "devices": ["cpu", 42],
                },
                "cuda": {
                    "state": "unsupported",
                    "message": "Unsupported GPU",
                },
                "custom": {"state": "Experimental State"},
            },
        }
    }
}


def test_normalize_backend_readiness_returns_typed_sorted_summary():
    result = normalize_backend_readiness(SYSTEM_INFO)

    assert result.status == "ready"
    assert result.available is True
    assert result.counts.model_dump() == {
        "installed": 1,
        "update_required": 1,
        "installable": 1,
        "unsupported": 1,
        "other": 1,
    }
    assert [item.state for item in result.items] == [
        "update_required",
        "installed",
        "installable",
        "experimental_state",
        "unsupported",
    ]
    rocm = result.items[0]
    assert rocm.recipe_name == "Llama.cpp GPU"
    assert rocm.action == "lemonade backends install llamacpp:rocm"
    assert rocm.release_url == "https://example.test/llama.cpp/b9752"
    assert rocm.download_filename == "llama-rocm.tar.gz"
    assert result.items[2].devices == ["cpu"]


@pytest.mark.parametrize("payload", [None, [], {}, {"recipes": []}])
def test_normalize_backend_readiness_degrades_for_missing_recipe_object(payload):
    result = normalize_backend_readiness(payload)

    assert result.status == "degraded"
    assert result.available is False
    assert result.items == []
    assert result.message


def test_normalize_backend_readiness_accepts_empty_recipes():
    result = normalize_backend_readiness({"recipes": {}})

    assert result.status == "empty"
    assert result.available is True
    assert result.counts.model_dump() == {
        "installed": 0,
        "update_required": 0,
        "installable": 0,
        "unsupported": 0,
        "other": 0,
    }


class FakeProvider:
    async def get_system_info(self):
        return SYSTEM_INFO


@pytest.mark.asyncio
async def test_backend_readiness_endpoint_uses_provider():
    result = await backend_readiness(provider=FakeProvider())

    assert result.status == "ready"
    assert result.counts.update_required == 1
