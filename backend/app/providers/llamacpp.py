"""Direct llama.cpp provider stub for future multi-runtime support."""
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


class LlamaCppDirectProvider(LLMProvider):
    """Stub provider for a direct llama.cpp server."""

    def __init__(self, url: str = "http://localhost:8080", admin_key: str | None = None):
        self.url = url
        self.admin_key = admin_key
        self.capabilities = Capabilities(
            health=True,
            stats=True,
            openai_models=True,
            load=False,
            unload=False,
            delete=False,
            pull=False,
        )

    async def get_health(self) -> LemonadeHealthResponse:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def get_stats(self) -> LemonadeStatsResponse:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def get_system_info(self) -> dict:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def list_models(self, include_catalog: bool = False) -> ModelsListResponse:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def get_running_models(self) -> RunningModelsResponse:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def show_model(self, name: str) -> ModelShowResponse:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def load_model(self, request: LoadModelRequest) -> LoadModelResponse:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def unload_model(self, model_name: str | None) -> bool:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def delete_model(self, name: str) -> bool:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def get_config(self) -> LemonadeConfigResponse:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")

    async def set_config(self, request: ConfigUpdateRequest) -> dict:
        raise NotImplementedError("LlamaCppDirectProvider is a M14 stub and is not active yet.")
