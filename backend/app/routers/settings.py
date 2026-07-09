"""Persistent settings endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.setup import (
    AppearanceConfig,
    ConnectionDoctorResponse,
    ConnectionTestResult,
    DiscoveryResult,
    LccConfigPublic,
    RuntimeConfig,
    RuntimeConfigPublic,
    SystemConfig,
)
from app.services.runtime_registry import RuntimeRegistry
from app.services.setup import SetupService

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_setup_service() -> SetupService:
    return SetupService()


@router.get("", response_model=LccConfigPublic)
async def get_settings(service: SetupService = Depends(get_setup_service)):
    return service.get_public_config()


@router.put("/system", response_model=LccConfigPublic)
async def update_system(
    system: SystemConfig,
    service: SetupService = Depends(get_setup_service),
):
    return service.update_system(system)


@router.put("/appearance", response_model=LccConfigPublic)
async def update_appearance(
    appearance: AppearanceConfig,
    service: SetupService = Depends(get_setup_service),
):
    return service.update_appearance(appearance)


@router.post("/runtimes", response_model=RuntimeConfigPublic, status_code=status.HTTP_201_CREATED)
async def add_runtime(
    runtime: RuntimeConfig,
    service: SetupService = Depends(get_setup_service),
):
    try:
        return service.add_runtime(runtime)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/runtimes/{runtime_id}", response_model=RuntimeConfigPublic)
async def update_runtime(
    runtime_id: str,
    runtime: RuntimeConfig,
    service: SetupService = Depends(get_setup_service),
):
    updated = service.update_runtime(runtime_id, runtime)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Runtime '{runtime_id}' not found")
    return updated


@router.delete("/runtimes/{runtime_id}")
async def remove_runtime(
    runtime_id: str,
    service: SetupService = Depends(get_setup_service),
):
    try:
        removed = service.remove_runtime(runtime_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail=f"Runtime '{runtime_id}' not found")
    return {"deleted": True}


@router.post("/runtimes/{runtime_id}/activate")
async def activate_runtime(
    runtime_id: str,
    service: SetupService = Depends(get_setup_service),
):
    config = service.get_config()
    candidate = next((runtime for runtime in config.runtimes if runtime.id == runtime_id), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Runtime '{runtime_id}' not found")
    if candidate.type != "lemonade":
        raise HTTPException(
            status_code=400,
            detail="Only Lemonade runtimes can be activated until multi-runtime routing is implemented.",
        )

    runtime = service.activate_runtime(runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail=f"Runtime '{runtime_id}' not found")
    RuntimeRegistry.instance().set_active(runtime)
    return {"active": runtime_id}


@router.post("/runtimes/{runtime_id}/test", response_model=ConnectionTestResult)
async def test_runtime(
    runtime_id: str,
    service: SetupService = Depends(get_setup_service),
):
    result = await service.test_saved_runtime(runtime_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Runtime '{runtime_id}' not found")
    return result


@router.post("/runtimes/{runtime_id}/discover", response_model=DiscoveryResult)
async def discover_runtime(
    runtime_id: str,
    service: SetupService = Depends(get_setup_service),
):
    result = await service.discover_saved_runtime(runtime_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Runtime '{runtime_id}' not found")
    return result


@router.post("/runtimes/{runtime_id}/doctor", response_model=ConnectionDoctorResponse)
async def connection_doctor(
    runtime_id: str,
    service: SetupService = Depends(get_setup_service),
):
    config = service.get_config()
    runtime = next((item for item in config.runtimes if item.id == runtime_id), None)
    if runtime is None:
        raise HTTPException(status_code=404, detail=f"Runtime '{runtime_id}' not found")
    return await service.connection_doctor(runtime)
