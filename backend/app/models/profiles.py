"""Pydantic schemas for per-model profiles."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    """Runtime and request defaults stored in a profile."""

    ctx_size: int | None = None
    global_timeout: int | None = None
    llamacpp_backend: str | None = None
    llamacpp_args: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    app_timeout: int | None = None
    stop_sequences: str | None = None


class Profile(BaseModel):
    """Saved configuration profile for a single model."""

    id: str
    name: str
    description: str = ""
    icon: str = "profile"
    config: ProfileConfig
    is_builtin: bool = False
    is_default: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ModelProfiles(BaseModel):
    """All profiles stored for a model."""

    model_name: str
    default_profile_id: str | None = None
    profiles: list[Profile] = Field(default_factory=list)


class SmartRecommendation(BaseModel):
    """Hardware-aware recommendation for a model."""

    model_name: str
    model_size_gb: float | None = None
    ram_total_gb: float
    ram_available_gb: float
    recommended_ctx: int
    safe_max_ctx: int
    risk_threshold_ctx: int
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProfileCreateRequest(BaseModel):
    name: str
    description: str = ""
    icon: str = "profile"
    config: ProfileConfig


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    config: ProfileConfig | None = None
    is_default: bool | None = None
