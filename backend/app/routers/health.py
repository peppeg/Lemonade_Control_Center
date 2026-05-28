"""
Health and capabilities endpoints.

These are the first endpoints to be implemented (M1) and serve as
the foundation for the frontend to understand what's available.
"""
import httpx
from fastapi import APIRouter

from app.config import settings
from app.capabilities import capabilities
from app.models.schemas import HealthResponse, CapabilitiesResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    LCC backend health check.

    Also probes Lemonade reachability (quick GET to /api/v1/health)
    to report if the underlying server is up.
    """
    lemonade_reachable = False
    lemonade_version = capabilities.lemonade_version

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.lemonade_url}/api/v1/health")
            if resp.status_code == 200:
                lemonade_reachable = True
                data = resp.json()
                lemonade_version = data.get("version", lemonade_version)
    except (httpx.ConnectError, httpx.TimeoutException):
        pass

    status = "ok" if lemonade_reachable else "degraded"

    return HealthResponse(
        status=status,
        app_name=settings.app_name,
        app_version=settings.app_version,
        lemonade_url=settings.lemonade_url,
        lemonade_reachable=lemonade_reachable,
        lemonade_version=lemonade_version,
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities():
    """
    Returns what features are available based on the M0 probe results
    and current configuration flags (ENABLE_DELETE, ENABLE_RESTART).

    The frontend uses this to enable/disable UI elements.
    """
    return CapabilitiesResponse(
        # Lemonade API
        health=capabilities.health,
        stats=capabilities.stats,
        system_info=capabilities.system_info,
        load=capabilities.load,
        unload=capabilities.unload,
        delete=capabilities.delete,
        delete_enabled=capabilities.delete and settings.enable_delete,
        pull=capabilities.pull,

        # Internal
        internal_config=capabilities.internal_config,
        internal_set=capabilities.internal_set,

        # Ollama
        ollama_tags=capabilities.ollama_tags,
        ollama_ps=capabilities.ollama_ps,
        ollama_show=capabilities.ollama_show,
        ollama_version=capabilities.ollama_version,

        # OpenAI
        openai_models=capabilities.openai_models,

        # WebSocket
        websocket=capabilities.websocket,
        websocket_port=capabilities.websocket_port,

        # System
        cmd_systemctl=capabilities.cmd_systemctl,
        cmd_journalctl=capabilities.cmd_journalctl,
        cmd_sensors=capabilities.cmd_sensors,
        restart_enabled=capabilities.cmd_systemctl and settings.enable_restart,
        bench_lab=settings.enable_bench_lab,

        # Meta
        lemonade_version=capabilities.lemonade_version,
        probe_timestamp=capabilities.probe_timestamp,
    )
