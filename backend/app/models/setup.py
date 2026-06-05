"""Schemas for setup wizard and persistent application settings."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RuntimeType = Literal["lemonade", "ollama", "llamacpp", "custom"]
AccessMode = Literal["local", "ssh_tunnel", "tailscale", "remote"]
RuntimeTestStatus = Literal["untested", "ok", "error"]
OsType = Literal["linux_systemd", "windows", "macos", "docker", "other"]
Theme = Literal["dark", "light", "system"]
SidebarPosition = Literal["left", "right"]
DiscoveryStatus = Literal["ok", "warning", "error", "skip"]


class RuntimeConfig(BaseModel):
    """Configuration for a single LLM runtime."""

    id: str
    type: RuntimeType
    name: str
    url: str
    admin_key: str | None = None
    is_active: bool = False
    access_mode: AccessMode = "local"
    capabilities_count: int = 0
    last_tested: datetime | None = None
    test_status: RuntimeTestStatus = "untested"


class RuntimeConfigPublic(BaseModel):
    """Runtime config returned to the frontend with secrets redacted."""

    id: str
    type: RuntimeType
    name: str
    url: str
    admin_key_configured: bool = False
    is_active: bool = False
    access_mode: AccessMode = "local"
    capabilities_count: int = 0
    last_tested: datetime | None = None
    test_status: RuntimeTestStatus = "untested"


class SystemConfig(BaseModel):
    """System-level configuration."""

    os_type: OsType = "linux_systemd"
    service_name: str = "lemond.service"
    enable_system_commands: bool = True
    enable_restart: bool = False
    enable_delete: bool = False


class AppearanceConfig(BaseModel):
    """UI appearance preferences."""

    theme: Theme = "dark"
    accent_color: str = "lemon"
    polling_interval_s: int = 5
    sidebar_position: SidebarPosition = "left"


class LccConfig(BaseModel):
    """Full application configuration saved to backend data/config.json."""

    setup_complete: bool = False
    setup_date: datetime | None = None
    version: str = "1.0.0"
    runtimes: list[RuntimeConfig] = Field(default_factory=list)
    active_runtime_id: str | None = None
    system: SystemConfig = Field(default_factory=SystemConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)


class LccConfigPublic(BaseModel):
    """Public config returned to the frontend."""

    setup_complete: bool = False
    setup_date: datetime | None = None
    version: str = "1.0.0"
    runtimes: list[RuntimeConfigPublic] = Field(default_factory=list)
    active_runtime_id: str | None = None
    system: SystemConfig = Field(default_factory=SystemConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)


class SetupStatusResponse(BaseModel):
    """Current setup status."""

    setup_complete: bool
    active_runtime_id: str | None = None


class SetupConnectionRequest(BaseModel):
    """Connection test request for a runtime."""

    type: Literal["lemonade", "ollama", "llamacpp"]
    url: str
    admin_key: str | None = None


class ConnectionTestResult(BaseModel):
    """Result of testing a runtime connection."""

    success: bool
    version: str | None = None
    models_count: int = 0
    error: str | None = None
    latency_ms: float = 0


class DiscoveryCheck(BaseModel):
    """Single discovery check result."""

    name: str
    endpoint: str
    status: DiscoveryStatus
    detail: str


class DiscoveryResult(BaseModel):
    """Result of auto-discovery for a runtime."""

    checks: list[DiscoveryCheck] = Field(default_factory=list)
    total: int = 0
    passed: int = 0
    capabilities_json: dict[str, bool] = Field(default_factory=dict)


class CompleteSetupRequest(BaseModel):
    """Finalize setup wizard configuration."""

    runtime: RuntimeConfig
    system: SystemConfig = Field(default_factory=SystemConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
