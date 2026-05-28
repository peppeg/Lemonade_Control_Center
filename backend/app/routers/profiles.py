"""Profile CRUD endpoints."""
from __future__ import annotations

import psutil
from fastapi import APIRouter, Depends, HTTPException

from app.models.profiles import (
    ModelProfiles,
    Profile,
    ProfileCreateRequest,
    ProfileUpdateRequest,
    SmartRecommendation,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def get_profile_service() -> ProfileService:
    return ProfileService()


@router.get("/{model_name}", response_model=ModelProfiles)
async def list_profiles(model_name: str, service: ProfileService = Depends(get_profile_service)):
    return service.list_profiles(model_name)


@router.post("/{model_name}", response_model=Profile, status_code=201)
async def create_profile(
    model_name: str,
    request: ProfileCreateRequest,
    service: ProfileService = Depends(get_profile_service),
):
    return service.create_profile(model_name, request)


@router.get("/{model_name}/recommendation", response_model=SmartRecommendation)
async def get_recommendation(
    model_name: str,
    model_size_gb: float | None = None,
    service: ProfileService = Depends(get_profile_service),
):
    memory = psutil.virtual_memory()
    return service.compute_recommendation(
        model_name=model_name,
        model_size_gb=model_size_gb,
        ram_total_gb=memory.total / (1024**3),
        ram_available_gb=memory.available / (1024**3),
    )


@router.get("/{model_name}/{profile_id}", response_model=Profile)
async def get_profile(
    model_name: str,
    profile_id: str,
    service: ProfileService = Depends(get_profile_service),
):
    profile = service.get_profile(model_name, profile_id)
    if profile is None:
        raise HTTPException(404, f"Profile '{profile_id}' not found")
    return profile


@router.put("/{model_name}/{profile_id}", response_model=Profile)
async def update_profile(
    model_name: str,
    profile_id: str,
    request: ProfileUpdateRequest,
    service: ProfileService = Depends(get_profile_service),
):
    profile = service.update_profile(model_name, profile_id, request)
    if profile is None:
        raise HTTPException(404, f"Profile '{profile_id}' not found")
    return profile


@router.delete("/{model_name}/{profile_id}")
async def delete_profile(
    model_name: str,
    profile_id: str,
    service: ProfileService = Depends(get_profile_service),
):
    if not service.delete_profile(model_name, profile_id):
        raise HTTPException(400, "Cannot delete built-in profile or profile not found")
    return {"deleted": True}


@router.post("/{model_name}/{profile_id}/clone", response_model=Profile)
async def clone_profile(
    model_name: str,
    profile_id: str,
    new_name: str = "Copy",
    service: ProfileService = Depends(get_profile_service),
):
    profile = service.clone_profile(model_name, profile_id, new_name)
    if profile is None:
        raise HTTPException(404, f"Source profile '{profile_id}' not found")
    return profile


@router.post("/{model_name}/{profile_id}/set-default")
async def set_default(
    model_name: str,
    profile_id: str,
    service: ProfileService = Depends(get_profile_service),
):
    if not service.set_default(model_name, profile_id):
        raise HTTPException(404, f"Profile '{profile_id}' not found")
    return {"default": profile_id}


@router.get("/{model_name}/{profile_id}/export")
async def export_profile(
    model_name: str,
    profile_id: str,
    service: ProfileService = Depends(get_profile_service),
):
    data = service.export_profile(model_name, profile_id)
    if data is None:
        raise HTTPException(404, f"Profile '{profile_id}' not found")
    return data


@router.post("/{model_name}/import", response_model=Profile)
async def import_profile(
    model_name: str,
    data: dict,
    service: ProfileService = Depends(get_profile_service),
):
    profile = service.import_profile(model_name, data)
    if profile is None:
        raise HTTPException(400, "Invalid profile data")
    return profile
