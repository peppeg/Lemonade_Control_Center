"""
FastAPI dependency injection for providers and services.

Usage in routers:
  @router.get("/models")
  async def list_models(provider: LemonadeProvider = Depends(get_provider)):
      return await provider.list_models()
"""
from functools import lru_cache

from app.providers.lemonade import LemonadeProvider


@lru_cache(maxsize=1)
def get_provider() -> LemonadeProvider:
    """Returns the singleton LemonadeProvider instance."""
    return LemonadeProvider()
