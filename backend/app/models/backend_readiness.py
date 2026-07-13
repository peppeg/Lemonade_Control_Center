"""Typed backend-readiness responses derived from Lemonade system info."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BackendReadinessItem(BaseModel):
    recipe_key: str
    recipe_name: str
    backend_key: str
    state: str = "unknown"
    version: str | None = None
    message: str = ""
    action: str = ""
    devices: list[str] = Field(default_factory=list)
    release_url: str | None = None
    download_filename: str | None = None
    experimental: bool = False


class BackendReadinessCounts(BaseModel):
    installed: int = 0
    update_required: int = 0
    installable: int = 0
    unsupported: int = 0
    other: int = 0


class BackendReadinessResponse(BaseModel):
    """Stable LCC view of Lemonade's recipe/backend readiness data."""

    status: Literal["ready", "empty", "degraded", "unavailable"]
    available: bool
    source: Literal["lemonade_system_info"] = "lemonade_system_info"
    message: str = ""
    counts: BackendReadinessCounts = Field(default_factory=BackendReadinessCounts)
    items: list[BackendReadinessItem] = Field(default_factory=list)


class BackendInstallRequest(BaseModel):
    recipe_key: str
    backend_key: str


class BackendInstallResponse(BaseModel):
    success: bool
    recipe_key: str
    backend_key: str
    previous_state: str
    message: str
    raw: dict = Field(default_factory=dict)
