"""Ollama provider stub for future multi-runtime support."""
from __future__ import annotations

from app.capabilities import Capabilities
from app.models.schemas import (
    ConfigUpdateRequest,
    LemonadeConfigResponse,
    LemonadeHealthResponse,
    LemonadeStatsResponse,
    LoadModelRequest,
    LoadModelResponse,
    ModelShowResponse,
    ModelsListResponse,
    RunningModelsResponse,
)
from app.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    """Stub provider for an Ollama runtime."""

    def __init__(self, url: str = "http://localhost:11434", admin_key: str | None = None):
        self.url = url
        self.admin_key = admin_key
        self.capabilities = Capabilities(
            health=True,
            ollama_tags=True,
            ollama_ps=True,
            ollama_show=True,
            ollama_version=True,
            pull=True,
            delete=True,
        )

    async def get_health(self) -> LemonadeHealthResponse:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def get_stats(self) -> LemonadeStatsResponse:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def get_system_info(self) -> dict:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def list_models(self, include_catalog: bool = False) -> ModelsListResponse:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def get_running_models(self) -> RunningModelsResponse:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def show_model(self, name: str) -> ModelShowResponse:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def load_model(self, request: LoadModelRequest) -> LoadModelResponse:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def unload_model(self, model_name: str | None) -> bool:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def delete_model(self, name: str) -> bool:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def get_config(self) -> LemonadeConfigResponse:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")

    async def set_config(self, request: ConfigUpdateRequest) -> dict:
        raise NotImplementedError("OllamaProvider is a M14 stub and is not active yet.")
