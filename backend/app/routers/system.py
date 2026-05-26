"""
System info and process management router.

Provides hardware stats, temperatures, llama-server process info,
systemd service status, and (gated) restart.
"""
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.capabilities import capabilities
from app.models.schemas import (
    HardwareInfo,
    TemperaturesResponse,
    TopProcessesResponse,
    LlamaServerInfoResponse,
    ServiceStatusResponse,
    RestartServiceResponse,
)
from app.services.hardware import (
    get_hardware_info,
    get_temperatures,
    get_top_processes,
)
from app.services.process import (
    find_llama_server,
    get_service_status,
    restart_service,
)

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/hardware", response_model=HardwareInfo)
async def hardware_info():
    """Get current hardware status (RAM, CPU, disk)."""
    return get_hardware_info()


@router.get("/temperatures", response_model=TemperaturesResponse)
async def temperatures():
    """Get temperature readings from sensors."""
    return get_temperatures()


@router.get("/processes", response_model=TopProcessesResponse)
async def top_processes():
    """Get top 10 processes sorted by memory usage."""
    return get_top_processes(n=10)


@router.get("/llama-server", response_model=LlamaServerInfoResponse)
async def llama_server_info():
    """Find llama-server process and parse its command line parameters."""
    return find_llama_server()


@router.get("/service", response_model=ServiceStatusResponse)
async def service_status():
    """Get lemond systemd service status."""
    if not capabilities.cmd_systemctl:
        return ServiceStatusResponse(
            active=False, status="not-found",
            raw_output="systemctl not available", available=False
        )
    return get_service_status()


@router.post("/restart", response_model=RestartServiceResponse)
async def restart_lemonade_service():
    """Restart lemond.service. Requires ENABLE_RESTART=true."""
    if not settings.enable_restart:
        raise HTTPException(
            403,
            "Service restart is disabled. Set ENABLE_RESTART=true in .env."
        )
    if not capabilities.cmd_systemctl:
        raise HTTPException(501, "systemctl not available on this system.")

    success, message = restart_service()
    return RestartServiceResponse(success=success, message=message)
