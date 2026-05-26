"""
LemonadeProvider — concrete implementation of LLMProvider for Lemonade Server.

All calls proxy through httpx to localhost:13305 (configurable).
Every method checks capabilities before calling — if the endpoint isn't
available, raises a clean error or returns a degraded response.
"""
import httpx
from fastapi import HTTPException

from app.config import settings
from app.capabilities import capabilities, Capabilities
from app.providers.base import LLMProvider
from app.models.schemas import (
    LemonadeHealthResponse,
    LemonadeStatsResponse,
    ModelsListResponse,
    ModelInfo,
    RunningModelsResponse,
    RunningModelInfo,
    ModelShowResponse,
    LoadModelRequest,
    LoadModelResponse,
    LemonadeConfigResponse,
    ConfigUpdateRequest,
)


class LemonadeProvider(LLMProvider):
    """Lemonade Server API provider."""

    def __init__(self):
        self.base_url = settings.lemonade_url
        self.capabilities = capabilities
        self.timeout = 30.0

        self.admin_headers: dict[str, str] | None = None
        if settings.lemonade_admin_api_key:
            self.admin_headers = {
                "Authorization": f"Bearer {settings.lemonade_admin_api_key}"
            }

    def _require_capability(self, cap_name: str, endpoint: str) -> None:
        """Raise 501 if a capability is not available."""
        if not getattr(self.capabilities, cap_name, False):
            raise HTTPException(
                status_code=501,
                detail=f"Capability '{cap_name}' not available. "
                       f"Endpoint {endpoint} did not respond in the probe. "
                       f"Re-run 'python capabilities/probe.py' after verifying Lemonade config."
            )

    async def _get(self, path: str, *, headers: dict | None = None,
                   timeout: float | None = None) -> httpx.Response:
        """GET request to Lemonade with error handling."""
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                return await client.get(
                    f"{self.base_url}{path}",
                    headers=headers
                )
        except httpx.ConnectError:
            raise HTTPException(503, f"Lemonade not reachable at {self.base_url}")
        except httpx.TimeoutException:
            raise HTTPException(504, f"Lemonade request timed out: {path}")

    async def _post(self, path: str, body: dict | None = None, *,
                    headers: dict | None = None,
                    timeout: float | None = None) -> httpx.Response:
        """POST request to Lemonade with error handling."""
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                return await client.post(
                    f"{self.base_url}{path}",
                    json=body or {},
                    headers=headers
                )
        except httpx.ConnectError:
            raise HTTPException(503, f"Lemonade not reachable at {self.base_url}")
        except httpx.TimeoutException:
            raise HTTPException(504, f"Lemonade request timed out: {path}")

    async def get_health(self) -> LemonadeHealthResponse:
        resp = await self._get("/api/v1/health")
        if resp.status_code != 200:
            return LemonadeHealthResponse(
                raw={"error": resp.text, "status_code": resp.status_code},
                status="error"
            )
        data = resp.json()
        return LemonadeHealthResponse(
            raw=data,
            version=data.get("version"),
            status=data.get("status", "unknown"),
            loaded_models=data.get("loaded_models", data.get("models", [])),
            websocket_port=data.get("websocket_port"),
        )

    async def get_stats(self) -> LemonadeStatsResponse:
        self._require_capability("stats", "/api/v1/stats")
        resp = await self._get("/api/v1/stats")
        if resp.status_code != 200:
            return LemonadeStatsResponse(raw={}, available=False)
        return LemonadeStatsResponse(raw=resp.json())

    async def get_system_info(self) -> dict:
        self._require_capability("system_info", "/api/v1/system-info")
        resp = await self._get("/api/v1/system-info")
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()

    async def list_models(self) -> ModelsListResponse:
        """List downloaded models. Prefers /api/tags (Ollama), falls back to /api/v1/models."""

        running_names: set[str] = set()
        try:
            running = await self.get_running_models()
            running_names = {m.name for m in running.models}
        except Exception:
            pass

        if self.capabilities.ollama_tags:
            resp = await self._get("/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("models", [])
                models = [
                    ModelInfo(
                        name=m.get("name", m.get("model", "unknown")),
                        model=m.get("model"),
                        size=m.get("size"),
                        digest=m.get("digest"),
                        modified_at=m.get("modified_at"),
                        details=m.get("details"),
                        is_loaded=m.get("name", "") in running_names,
                    )
                    for m in raw_models
                ]
                return ModelsListResponse(models=models, source="ollama_tags")

        if self.capabilities.openai_models:
            resp = await self._get("/api/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("data", [])
                models = [
                    ModelInfo(
                        name=m.get("id", "unknown"),
                        model=m.get("id"),
                        is_loaded=m.get("id", "") in running_names,
                    )
                    for m in raw_models
                ]
                return ModelsListResponse(models=models, source="openai_models")

        return ModelsListResponse(models=[], source="none")

    async def get_running_models(self) -> RunningModelsResponse:
        """Get currently loaded models via /api/ps."""
        self._require_capability("ollama_ps", "/api/ps")
        resp = await self._get("/api/ps")
        if resp.status_code != 200:
            return RunningModelsResponse(models=[])
        data = resp.json()
        models = [
            RunningModelInfo(
                name=m.get("name", "unknown"),
                model=m.get("model"),
                size=m.get("size"),
                digest=m.get("digest"),
                expires_at=m.get("expires_at"),
                size_vram=m.get("size_vram"),
                details=m.get("details"),
            )
            for m in data.get("models", [])
        ]
        return RunningModelsResponse(models=models)

    async def show_model(self, name: str) -> ModelShowResponse:
        """Get detailed info about a model via /api/show."""
        self._require_capability("ollama_show", "/api/show")
        resp = await self._post("/api/show", {"name": name})
        if resp.status_code != 200:
            return ModelShowResponse(raw={"error": resp.text}, available=False)
        return ModelShowResponse(raw=resp.json())

    async def load_model(self, request: LoadModelRequest) -> LoadModelResponse:
        body: dict = {"model_name": request.model_name}
        if request.ctx_size is not None:
            body["ctx_size"] = request.ctx_size
        if request.llamacpp_backend is not None:
            body["llamacpp_backend"] = request.llamacpp_backend
        if request.llamacpp_args is not None:
            body["llamacpp_args"] = request.llamacpp_args
        if request.save_options:
            body["save_options"] = True

        resp = await self._post("/api/v1/load", body, timeout=300.0)

        if resp.status_code == 200:
            return LoadModelResponse(
                success=True, message=f"Model '{request.model_name}' loaded.",
                raw=resp.json()
            )
        else:
            return LoadModelResponse(
                success=False,
                message=f"Load failed ({resp.status_code}): {resp.text[:300]}",
                raw=None
            )

    async def unload_model(self, model_name: str | None = None) -> bool:
        body = {}
        if model_name:
            body["model_name"] = model_name

        resp = await self._post("/api/v1/unload", body, timeout=30.0)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, f"Unload failed: {resp.text[:300]}")
        return True

    async def delete_model(self, name: str) -> bool:
        if not settings.enable_delete:
            raise HTTPException(
                403,
                "Delete is disabled. Set ENABLE_DELETE=true in .env to enable."
            )

        resp = await self._post("/api/v1/delete", {"model_name": name})
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, f"Delete failed: {resp.text[:300]}")
        return True

    async def get_config(self) -> LemonadeConfigResponse:
        self._require_capability("internal_config", "/internal/config")
        if not self.admin_headers:
            raise HTTPException(
                403,
                "Admin API key required. Set LEMONADE_ADMIN_API_KEY in .env."
            )
        resp = await self._get("/internal/config", headers=self.admin_headers)
        if resp.status_code != 200:
            return LemonadeConfigResponse(raw={"error": resp.text}, available=False)
        return LemonadeConfigResponse(raw=resp.json())

    async def set_config(self, request: ConfigUpdateRequest) -> dict:
        self._require_capability("internal_set", "/internal/set")
        if not self.admin_headers:
            raise HTTPException(
                403,
                "Admin API key required. Set LEMONADE_ADMIN_API_KEY in .env."
            )
        resp = await self._post(
            "/internal/set", request.updates, headers=self.admin_headers
        )
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, f"Config update failed: {resp.text[:300]}")
        return resp.json()
