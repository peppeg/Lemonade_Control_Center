"""
Router that proxies all Lemonade API calls through the LemonadeProvider.

Every endpoint is capability-driven: if the underlying Lemonade endpoint
isn't available, the provider raises a clean 501 error.
"""
from fastapi import APIRouter, Depends, Query

from app.dependencies import get_provider
from app.providers.lemonade import LemonadeProvider
from app.models.schemas import (
    LemonadeHealthResponse,
    LemonadeStatsResponse,
    ModelsListResponse,
    RunningModelsResponse,
    ModelShowResponse,
    LoadModelRequest,
    LoadModelResponse,
    PullModelRequest,
    PullModelResponse,
    UnloadModelRequest,
    LemonadeConfigResponse,
    LemonadeSavedOptionsResponse,
    ConfigUpdateRequest,
)
from app.services.lemonade_options import read_saved_options

router = APIRouter(prefix="/api/lemonade", tags=["lemonade"])


@router.get("/health", response_model=LemonadeHealthResponse)
async def lemonade_health(provider: LemonadeProvider = Depends(get_provider)):
    """Get Lemonade server health status."""
    return await provider.get_health()


@router.get("/stats", response_model=LemonadeStatsResponse)
async def lemonade_stats(provider: LemonadeProvider = Depends(get_provider)):
    """Get performance stats from last Lemonade request."""
    return await provider.get_stats()


@router.get("/system-info")
async def lemonade_system_info(provider: LemonadeProvider = Depends(get_provider)):
    """Get Lemonade system/device info."""
    return await provider.get_system_info()


@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    catalog: bool = Query(default=False),
    provider: LemonadeProvider = Depends(get_provider),
):
    """List downloaded models, optionally including the Lemonade catalog."""
    return await provider.list_models(include_catalog=catalog)


@router.get("/running", response_model=RunningModelsResponse)
async def running_models(provider: LemonadeProvider = Depends(get_provider)):
    """List currently loaded/running models."""
    return await provider.get_running_models()


@router.get("/saved-options", response_model=LemonadeSavedOptionsResponse)
async def saved_options(model_name: str | None = None):
    """Read Lemonade's official saved per-model load options."""
    return read_saved_options(model_name)


@router.get("/models/{model_name}", response_model=ModelShowResponse)
async def show_model(
    model_name: str,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Get detailed info about a specific model."""
    return await provider.show_model(model_name)


@router.post("/load", response_model=LoadModelResponse)
async def load_model(
    request: LoadModelRequest,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Load a model into memory with optional configuration."""
    return await provider.load_model(request)


@router.post("/pull", response_model=PullModelResponse)
async def pull_model(
    request: PullModelRequest,
    provider: LemonadeProvider = Depends(get_provider),
):
    """Download/install a registered Lemonade model."""
    return await provider.pull_model(request)


@router.post("/unload")
async def unload_model(
    request: UnloadModelRequest,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Unload a model from memory."""
    return await provider.unload_model(request.model_name)


@router.delete("/models/{model_name}")
async def delete_model(
    model_name: str,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Delete a model from disk. Requires ENABLE_DELETE=true."""
    await provider.delete_model(model_name)
    return {"success": True, "message": f"Model '{model_name}' deleted."}


@router.get("/config", response_model=LemonadeConfigResponse)
async def get_config(provider: LemonadeProvider = Depends(get_provider)):
    """Get current Lemonade config. Requires admin API key."""
    return await provider.get_config()


@router.post("/config")
async def update_config(
    request: ConfigUpdateRequest,
    provider: LemonadeProvider = Depends(get_provider)
):
    """Update Lemonade config. Requires admin API key."""
    return await provider.set_config(request)
