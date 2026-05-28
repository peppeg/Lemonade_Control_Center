"""
Abstract base class for LLM runtime providers.

Each provider (Lemonade, Ollama, llama.cpp direct...) implements this interface.
The router layer calls provider methods without knowing which runtime is behind it.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.capabilities import Capabilities
from app.models.schemas import (
    LemonadeHealthResponse,
    LemonadeStatsResponse,
    ModelsListResponse,
    RunningModelsResponse,
    ModelShowResponse,
    LoadModelRequest,
    LoadModelResponse,
    LemonadeConfigResponse,
    ConfigUpdateRequest,
)


class LLMProvider(ABC):
    """Interface that all runtime providers must implement."""

    capabilities: Capabilities

    @abstractmethod
    async def get_health(self) -> LemonadeHealthResponse:
        """Get runtime health status."""
        ...

    @abstractmethod
    async def get_stats(self) -> LemonadeStatsResponse:
        """Get performance stats from last request."""
        ...

    @abstractmethod
    async def get_system_info(self) -> dict:
        """Get runtime system/device info."""
        ...

    @abstractmethod
    async def list_models(self, include_catalog: bool = False) -> ModelsListResponse:
        """List all downloaded/available models."""
        ...

    @abstractmethod
    async def get_running_models(self) -> RunningModelsResponse:
        """List currently loaded models."""
        ...

    @abstractmethod
    async def show_model(self, name: str) -> ModelShowResponse:
        """Get detailed info about a specific model."""
        ...

    @abstractmethod
    async def load_model(self, request: LoadModelRequest) -> LoadModelResponse:
        """Load a model into memory."""
        ...

    @abstractmethod
    async def unload_model(self, model_name: str | None) -> bool:
        """Unload a model from memory."""
        ...

    @abstractmethod
    async def delete_model(self, name: str) -> bool:
        """Delete a model from disk."""
        ...

    @abstractmethod
    async def get_config(self) -> LemonadeConfigResponse:
        """Get current runtime config."""
        ...

    @abstractmethod
    async def set_config(self, request: ConfigUpdateRequest) -> dict:
        """Update runtime config."""
        ...
