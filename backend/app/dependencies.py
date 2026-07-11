"""
FastAPI dependency injection for providers and services.

Usage in routers:
  @router.get("/models")
  async def list_models(provider: LemonadeProvider = Depends(get_provider)):
      return await provider.list_models()
"""
from fastapi import Depends

from app.providers.lemonade import LemonadeProvider
from app.models.setup import RuntimeConfig
from app.services.completion_runner import CompletionRunner
from app.services.setup import SetupService


def get_active_runtime_config() -> RuntimeConfig | None:
    """Return the configured active runtime, if one is persisted."""
    service = SetupService()
    if not service.config_file.exists():
        return None
    config = service.get_config()
    return next(
        (runtime for runtime in config.runtimes if runtime.id == config.active_runtime_id),
        None,
    )


def get_provider() -> LemonadeProvider:
    """Return the active Lemonade provider.

    M14 prepares multiple runtime records, but existing API routes still proxy
    Lemonade endpoints. Only active runtimes of type "lemonade" are wired here.
    """
    active = get_active_runtime_config()
    if active and active.type == "lemonade":
        return LemonadeProvider(
            url=active.url,
            admin_key=active.admin_key,
            use_settings_admin_key=False,
        )
    return LemonadeProvider()


def get_completion_runner(
    provider: LemonadeProvider = Depends(get_provider),
) -> CompletionRunner:
    """Build the core completion runner for the active Lemonade runtime."""
    return CompletionRunner(provider.base_url)
