"""Pydantic schemas for Bench Lab."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from pydantic import BaseModel, Field


class BenchPrompt(BaseModel):
    id: str
    name: str
    prompt: str
    system_prompt: str = ""
    max_tokens: int = 4000
    temperature: float = 0.7
    app_timeout_seconds: int = 3600
    stop_sequences: list[str] = Field(default_factory=list)
    expected_format: str | None = None
    tags: list[str] = Field(default_factory=list)


class BenchSuite(BaseModel):
    id: str
    name: str
    description: str
    icon: str = "bench"
    prompts: list[BenchPrompt]
    recommended_ctx: int = 16384
    recommended_temp: float = 0.7
    estimated_minutes: int = 15


class BenchResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt_id: str
    prompt_name: str
    prompt: str = ""
    system_prompt: str = ""
    request_max_tokens: int | None = None
    request_temperature: float | None = None
    request_timeout_seconds: int | None = None
    request_stop_sequences: list[str] = Field(default_factory=list)
    model: str
    requested_model_name: str | None = None
    observed_model_name: str | None = None
    runtime_id: str | None = None
    runtime_label: str | None = None
    runtime_server_url: str | None = None
    workflow_profile_id: str | None = None
    workflow_profile_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_eval_tps: float = 0
    generation_tps: float = 0
    ttft_seconds: float = 0
    total_seconds: float = 0
    finish_reason: str = "unknown"
    finish_confidence: str = "unknown"
    response_preview: str = ""
    response_full: str = ""
    reasoning_text: str = ""
    token_count_source: str = "unavailable"
    completion_endpoint: str | None = None
    warnings: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    observed_backend: str | None = None
    observed_ctx_size: int | None = None
    observed_pid: int | None = None
    process_rss_gb: float | None = None
    ram_used_before_gb: float | None = None
    ram_used_after_gb: float | None = None
    swap_used_before_gb: float | None = None
    swap_used_after_gb: float | None = None
    manual_quality_score: int | None = Field(default=None, ge=1, le=5)
    manual_notes: str = ""


class SuiteResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    suite_id: str
    suite_name: str
    model: str
    requested_model_name: str | None = None
    observed_model_name: str | None = None
    runtime_id: str | None = None
    runtime_label: str | None = None
    runtime_server_url: str | None = None
    workflow_profile_id: str | None = None
    workflow_profile_name: str | None = None
    results: list[BenchResult]
    avg_gen_tps: float
    avg_ttft: float
    total_tokens: int
    total_seconds: float
    truncated_count: int
    error_count: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    manual_quality_score: int | None = Field(default=None, ge=1, le=5)
    manual_notes: str = ""


class BenchRunRequest(BaseModel):
    model: str
    prompt: str | None = None
    suite_id: str | None = None
    max_tokens: int = 4000
    temperature: float = 0.7
    system_prompt: str = ""
    workflow_profile_id: str | None = None
    workflow_profile_name: str | None = None


class BenchAnnotationRequest(BaseModel):
    manual_quality_score: int | None = Field(default=None, ge=1, le=5)
    manual_notes: str = ""


class BenchComparison(BaseModel):
    suite_id: str
    suite_name: str
    result_ids: list[str]
    results: list[SuiteResult]
