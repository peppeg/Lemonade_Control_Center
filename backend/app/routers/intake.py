"""Guided Hugging Face intake endpoints."""
from __future__ import annotations

import httpx
import psutil
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_provider
from app.models.intake import (
    IntakeInspectRequest,
    IntakeProfileRequest,
    IntakeProfileResponse,
    IntakePullRequest,
    IntakeReport,
    IntakeSearchRequest,
    IntakeSearchResponse,
)
from app.models.profiles import ProfileConfig, ProfileCreateRequest
from app.models.schemas import PullModelResponse
from app.providers.lemonade import LemonadeProvider
from app.routers.profiles import get_profile_service
from app.services.huggingface_intake import HuggingFaceIntakeService
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/api/intake", tags=["intake"])


@router.post("/search", response_model=IntakeSearchResponse)
async def search_repositories(
    request: IntakeSearchRequest,
    provider: LemonadeProvider = Depends(get_provider),
):
    try:
        results = await HuggingFaceIntakeService(provider).search(request.query)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, f"Repository search failed: {exc}") from exc
    return IntakeSearchResponse(query=request.query, results=results)


@router.post("/inspect", response_model=IntakeReport)
async def inspect_repository(
    request: IntakeInspectRequest,
    provider: LemonadeProvider = Depends(get_provider),
):
    try:
        return await HuggingFaceIntakeService(provider).inspect(request.repo_id)
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/profile", response_model=IntakeProfileResponse, status_code=201)
async def create_intake_profile(
    request: IntakeProfileRequest,
    service: ProfileService = Depends(get_profile_service),
):
    model_name = request.model_name.strip()
    if not model_name.startswith("user."):
        raise HTTPException(400, "Intake profiles must target a user.* Lemonade model name.")
    profile_model_name = model_name.removeprefix("user.")
    size_gb = request.variant_size_bytes / 1024**3 if request.variant_size_bytes else None
    memory = psutil.virtual_memory()
    recommendation = service.compute_recommendation(
        model_name=profile_model_name,
        model_size_gb=size_gb,
        ram_total_gb=memory.total / 1024**3,
        ram_available_gb=memory.available / 1024**3,
        model_loaded=False,
    )
    caveats = [
        "Memory impact is estimated from repository file size; validate with a real load attempt.",
        "Lemonade owns registration, download, import, and update detection.",
    ]
    profile = service.create_profile(
        profile_model_name,
        ProfileCreateRequest(
            name=request.profile_name,
            description=f"Guided intake for {request.repo_id}:{request.variant_name}.",
            intent=request.intent,
            notes=f"Source: {request.repo_id}; selected variant: {request.variant_name}; Lemonade registration: {model_name}.",
            known_caveats=caveats,
            runtime_id=request.runtime_id,
            icon="profile",
            config=ProfileConfig(
                ctx_size=min(recommendation.recommended_ctx, 32768),
                global_timeout=600,
                llamacpp_backend="vulkan",
                max_tokens=4000,
                temperature=0.7,
                app_timeout=300,
            ),
        ),
    )
    return IntakeProfileResponse(model_name=profile_model_name, profile_id=profile.id, profile_name=profile.name)


@router.post("/pull", response_model=PullModelResponse)
async def pull_intake_model(
    request: IntakePullRequest,
    provider: LemonadeProvider = Depends(get_provider),
):
    """Explicit operator action; Lemonade remains the lifecycle owner."""
    return await provider.pull_intake_model(request)
