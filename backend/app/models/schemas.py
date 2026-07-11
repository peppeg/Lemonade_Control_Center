"""
Pydantic schemas for the entire LCC backend.

Naming convention:
  - *Response: returned to the frontend
  - *Request: received from the frontend
  - *Info: internal data structures
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# Health & Capabilities (da M1, invariati)
# ═══════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    lemonade_url: str
    lemonade_reachable: bool
    lemonade_version: str | None


class CapabilitiesResponse(BaseModel):
    health: bool
    stats: bool
    system_info: bool
    load: bool
    unload: bool
    delete: bool
    delete_enabled: bool
    pull: bool
    internal_config: bool
    internal_set: bool
    ollama_tags: bool
    ollama_ps: bool
    ollama_show: bool
    ollama_version: bool
    openai_models: bool
    websocket: bool
    websocket_port: int | None
    cmd_systemctl: bool
    cmd_journalctl: bool
    cmd_sensors: bool
    restart_enabled: bool
    bench_lab: bool
    lemonade_version: str | None
    probe_timestamp: str | None


# ═══════════════════════════════════════════════════════════
# Fase 2.1 — Lemonade Models & Responses
# ═══════════════════════════════════════════════════════════

class LemonadeHealthResponse(BaseModel):
    """Proxied response from Lemonade /api/v1/health."""
    raw: dict
    version: str | None = None
    status: str = "unknown"
    loaded_models: list[dict] = Field(default_factory=list)
    websocket_port: int | None = None


class LemonadeStatsResponse(BaseModel):
    """Proxied response from Lemonade /api/v1/stats."""
    raw: dict
    available: bool = True


class ModelInfo(BaseModel):
    """A single model from the models list."""
    name: str
    model: str | None = None
    size: int | None = None
    digest: str | None = None
    modified_at: str | None = None
    details: dict | None = None
    is_loaded: bool = False
    downloaded: bool = True


class ModelsListResponse(BaseModel):
    """List of downloaded models."""
    models: list[ModelInfo] = Field(default_factory=list)
    source: Literal["ollama_tags", "openai_models", "merged_catalog", "none"] = "none"


class RunningModelInfo(BaseModel):
    """A currently loaded/running model."""
    name: str
    model: str | None = None
    size: int | None = None
    digest: str | None = None
    expires_at: str | None = None
    size_vram: int | None = None
    details: dict | None = None


class RunningModelsResponse(BaseModel):
    """List of currently running models."""
    models: list[RunningModelInfo] = Field(default_factory=list)


class ModelShowResponse(BaseModel):
    """Detailed info about a specific model."""
    raw: dict
    available: bool = True


class LoadModelRequest(BaseModel):
    """Request to load a model."""
    model_name: str
    ctx_size: int | None = None
    llamacpp_backend: str | None = None
    llamacpp_args: str | None = None
    merge_args: bool | None = None
    save_options: bool = False
    workflow_profile_id: str | None = None
    workflow_profile_name: str | None = None


class LoadModelResponse(BaseModel):
    """Response from loading a model."""
    success: bool
    message: str
    raw: dict | None = None
    evidence: RunEvidenceSeed | None = None


class SmokeTestRequest(BaseModel):
    """Small post-load request used to verify a loaded model."""
    model_name: str
    prompt: str = "Reply with exactly: LCC_SMOKE_OK"
    max_tokens: int = Field(default=32, ge=1, le=256)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    app_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    stop_sequences: list[str] = Field(default_factory=list)
    workflow_profile_id: str | None = None
    workflow_profile_name: str | None = None


class LogEntryLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    UPDATE = "update"
    BACKEND = "backend"
    PERFORMANCE = "performance"
    MODEL = "model"
    GENERATION = "generation"
    SLOT = "slot"


class LogEntry(BaseModel):
    """A single parsed log entry."""
    timestamp: str | None = None
    level: LogEntryLevel = LogEntryLevel.INFO
    message: str
    raw: str
    icon: str = "ℹ️"


class RunEvidenceSeed(BaseModel):
    """Minimal evidence record for one operator-triggered request."""
    id: str
    kind: Literal["smoke_test", "load_attempt"] = "smoke_test"
    model_name: str
    requested_model_name: str | None = None
    observed_model_name: str | None = None
    runtime_id: str | None = None
    runtime_label: str | None = None
    runtime_server_url: str | None = None
    workflow_profile_id: str | None = None
    workflow_profile_name: str | None = None
    prompt: str = ""
    response_text: str = ""
    reasoning_text: str = ""
    success: bool = False
    error: str | None = None
    load_message: str | None = None
    requested_backend: str | None = None
    requested_ctx_size: int | None = None
    requested_llamacpp_args: str | None = None
    request_max_tokens: int | None = None
    request_temperature: float | None = None
    request_timeout_seconds: int | None = None
    request_stop_sequences: list[str] = Field(default_factory=list)
    completion_endpoint: str | None = None
    completion_error_kind: str | None = None
    token_count_source: str = "unavailable"
    merge_args: bool | None = None
    save_options: bool | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_eval_tps: float = 0
    generation_tps: float = 0
    ttft_seconds: float = 0
    total_seconds: float = 0
    finish_reason: str = "unknown"
    finish_confidence: str = "unknown"
    observed_pid: int | None = None
    observed_backend: str | None = None
    observed_ctx_size: int | None = None
    process_rss_gb: float | None = None
    ram_used_before_gb: float | None = None
    ram_used_after_gb: float | None = None
    swap_used_before_gb: float | None = None
    swap_used_after_gb: float | None = None
    log_window_started_at: datetime | None = None
    log_window_ended_at: datetime | None = None
    log_source: Literal["journalctl", "unavailable", "error"] = "unavailable"
    log_entries: list[LogEntry] = Field(default_factory=list)
    log_capture_error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SmokeTestResponse(BaseModel):
    """Smoke test response and stored evidence seed."""
    success: bool
    message: str
    evidence: RunEvidenceSeed


class RunEvidenceListResponse(BaseModel):
    """Stored local run evidence seeds."""
    results: list[RunEvidenceSeed] = Field(default_factory=list)
    total: int = 0


class PullModelRequest(BaseModel):
    """Request to download/install a registered Lemonade model."""
    model_name: str


class PullModelResponse(BaseModel):
    """Response from pulling a model."""
    success: bool
    message: str
    raw: dict | None = None


class UnloadModelRequest(BaseModel):
    """Request to unload a model."""
    model_name: str | None = None


class ConfigUpdateRequest(BaseModel):
    """Request to update Lemonade config via /internal/set."""
    updates: dict


class LemonadeConfigResponse(BaseModel):
    """Current Lemonade configuration."""
    raw: dict
    available: bool = True


class LemonadeSavedOptionsResponse(BaseModel):
    """Saved per-model Lemonade load options from recipe_options.json."""
    available: bool = False
    path: str
    options: dict[str, dict] = Field(default_factory=dict)
    model_name: str | None = None
    selected_key: str | None = None
    selected_options: dict | None = None
    error: str | None = None


# ═══════════════════════════════════════════════════════════
# Fase 2.2 — System & Process
# ═══════════════════════════════════════════════════════════

class HardwareInfo(BaseModel):
    """System hardware status snapshot."""
    ram_total_gb: float
    ram_used_gb: float
    ram_available_gb: float
    ram_percent: float
    swap_total_gb: float
    swap_used_gb: float
    cpu_percent: float
    cpu_count: int
    gpu_available: bool = False
    gpu_name: str | None = None
    gpu_load_percent: float | None = None
    gpu_temp_c: float | None = None
    disk_total_gb: float | None = None
    disk_used_gb: float | None = None
    disk_free_gb: float | None = None
    disk_percent: float | None = None
    disk_path: str | None = None


class TemperatureReading(BaseModel):
    """A single temperature sensor reading."""
    label: str
    current: float
    high: float | None = None
    critical: float | None = None


class TemperaturesResponse(BaseModel):
    """Temperature readings from sensors."""
    readings: list[TemperatureReading] = Field(default_factory=list)
    available: bool = True
    error: str | None = None


class ProcessInfo(BaseModel):
    """Info about a running process (llama-server)."""
    pid: int
    name: str
    cpu_percent: float
    rss_gb: float
    vms_gb: float
    status: str
    create_time: datetime | None = None
    uptime_seconds: float | None = None


class LlamaServerParams(BaseModel):
    """Parsed parameters from llama-server command line."""
    executable: str | None = None
    model_path: str | None = None
    ctx_size: int | None = None
    port: int | None = None
    host: str | None = None
    ngl: int | None = None
    backend: str | None = None
    mmap: bool | None = None
    jinja: bool = False
    mmproj: str | None = None
    context_shift: bool | None = None
    keep: int | None = None
    reasoning_format: str | None = None
    spec_type: str | None = None
    spec_draft_n_max: int | None = None
    spec_draft_p_min: float | None = None
    raw_cmdline: str = ""


class LlamaServerInfoResponse(BaseModel):
    """Complete info about the running llama-server process."""
    found: bool = False
    process: ProcessInfo | None = None
    params: LlamaServerParams | None = None


class ServiceStatusResponse(BaseModel):
    """Status of the lemond systemd service."""
    active: bool = False
    status: str = "unknown"
    raw_output: str = ""
    available: bool = True


class TopProcessInfo(BaseModel):
    """A top process by memory usage."""
    pid: int
    name: str
    rss_gb: float
    cpu_percent: float


class TopProcessesResponse(BaseModel):
    """Top processes sorted by memory."""
    processes: list[TopProcessInfo] = Field(default_factory=list)


class RestartServiceResponse(BaseModel):
    """Response from restarting the Lemonade service."""
    success: bool
    message: str


# ═══════════════════════════════════════════════════════════
# Fase 2.3 — Logs & Stats
# ═══════════════════════════════════════════════════════════

class FinishReasonConfidence(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class FinishReason(BaseModel):
    """Finish reason with confidence level and evidence."""
    reason: Literal["length", "stop", "unknown"] = "unknown"
    confidence: FinishReasonConfidence = FinishReasonConfidence.UNKNOWN
    evidence: str = ""


class LastTaskStats(BaseModel):
    """Parsed statistics from the last completed task."""
    available: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    prompt_eval_tps: float | None = None
    generation_tps: float | None = None
    ttft_seconds: float | None = None
    total_duration_seconds: float | None = None
    finish_reason: FinishReason = Field(default_factory=FinishReason)
    truncated: bool | None = None
    raw_log_lines: list[str] = Field(default_factory=list)


class RecentLogsResponse(BaseModel):
    """Parsed recent log entries."""
    entries: list[LogEntry] = Field(default_factory=list)
    total_lines: int = 0
    source: str = "journalctl"


# ═══════════════════════════════════════════════════════════
# Diagnostic Bundle
# ═══════════════════════════════════════════════════════════

class DiagnosticMeta(BaseModel):
    """Metadata included in diagnostic bundles."""
    timestamp: str
    app_name: str
    app_version: str
    lemonade_url: str
    lemonade_version: str | None
    probe_timestamp: str | None
    os_info: str
