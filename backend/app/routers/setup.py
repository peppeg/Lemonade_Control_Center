"""Setup wizard endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.models.setup import (
    CompleteSetupRequest,
    ConnectionTestResult,
    DiscoveryResult,
    LemonadeDiscoveryResponse,
    LccConfigPublic,
    RuntimeConfig,
    SetupConnectionRequest,
    SetupStatusResponse,
)
from app.services.setup import SetupService

router = APIRouter(prefix="/api/setup", tags=["setup"])


def get_setup_service() -> SetupService:
    return SetupService()


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status(service: SetupService = Depends(get_setup_service)):
    config = service.get_config()
    return SetupStatusResponse(
        setup_complete=config.setup_complete,
        active_runtime_id=config.active_runtime_id,
    )


@router.post("/test-connection", response_model=ConnectionTestResult)
async def test_connection(
    request: SetupConnectionRequest,
    service: SetupService = Depends(get_setup_service),
):
    return await service.test_connection(request)


@router.post("/discover", response_model=DiscoveryResult)
async def discover(
    runtime: RuntimeConfig,
    service: SetupService = Depends(get_setup_service),
):
    return await service.run_discovery(runtime)


@router.get("/discover-lemonade", response_model=LemonadeDiscoveryResponse)
async def discover_lemonade(
    listen_ms: int = 2500,
    service: SetupService = Depends(get_setup_service),
):
    return await service.discover_lemonade_servers(listen_ms=listen_ms)


@router.post("/complete", response_model=LccConfigPublic)
async def complete_setup(
    request: CompleteSetupRequest,
    service: SetupService = Depends(get_setup_service),
):
    return service.complete_setup(request)
