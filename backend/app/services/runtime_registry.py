"""Registry for configured LLM runtime providers."""
from __future__ import annotations

from app.models.setup import RuntimeConfig
from app.providers.base import LLMProvider
from app.providers.lemonade import LemonadeProvider


class RuntimeRegistry:
    """Singleton registry used by settings to prepare multi-runtime support."""

    _instance: RuntimeRegistry | None = None

    def __init__(self):
        self._providers: dict[str, type[LLMProvider]] = {}
        self._active: LLMProvider | None = None
        self._active_config: RuntimeConfig | None = None
        self.register("lemonade", LemonadeProvider)

        from app.providers.llamacpp import LlamaCppDirectProvider
        from app.providers.ollama import OllamaProvider

        self.register("ollama", OllamaProvider)
        self.register("llamacpp", LlamaCppDirectProvider)

    @classmethod
    def instance(cls) -> RuntimeRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, runtime_type: str, provider: type[LLMProvider]) -> None:
        self._providers[runtime_type] = provider

    def provider_types(self) -> list[str]:
        return sorted(self._providers)

    def set_active(self, config: RuntimeConfig) -> LLMProvider:
        provider_cls = self._providers.get(config.type)
        if provider_cls is None:
            raise ValueError(f"Unknown runtime type: {config.type}")

        if config.type == "lemonade":
            provider = provider_cls(
                url=config.url,
                admin_key=config.admin_key,
                use_settings_admin_key=False,
            )
        else:
            provider = provider_cls(url=config.url, admin_key=config.admin_key)

        self._active = provider
        self._active_config = config
        return provider

    def get_active(self) -> LLMProvider | None:
        return self._active

    def get_active_config(self) -> RuntimeConfig | None:
        return self._active_config
