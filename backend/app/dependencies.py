"""
FastAPI dependency injection for providers and services.

Usage in routers:
  @router.get("/models")
  async def list_models(provider: LemonadeProvider = Depends(get_provider)):
      return await provider.list_models()
"""
from app.providers.lemonade import LemonadeProvider
from app.services.setup import SetupService


def get_provider() -> LemonadeProvider:
    """Return the active Lemonade provider.

    M14 prepares multiple runtime records, but existing API routes still proxy
    Lemonade endpoints. Only active runtimes of type "lemonade" are wired here.
    """
    service = SetupService()
    if not service.config_file.exists():
        return LemonadeProvider()

    config = service.get_config()
    active = next(
        (runtime for runtime in config.runtimes if runtime.id == config.active_runtime_id),
        None,
    )
    if active and active.type == "lemonade":
        return LemonadeProvider(
            url=active.url,
            admin_key=active.admin_key,
            use_settings_admin_key=False,
        )
    return LemonadeProvider()
