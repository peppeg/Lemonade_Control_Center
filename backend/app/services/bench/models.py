"""Pydantic schemas for Bench Lab."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BenchPrompt(BaseModel):
    id: str
    name: str
    prompt: str
    system_prompt: str = ""
    max_tokens: int = 4000
    temperature: float = 0.7
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
    prompt_id: str
    prompt_name: str
    model: str
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error: str | None = None


class SuiteResult(BaseModel):
    suite_id: str
    suite_name: str
    model: str
    results: list[BenchResult]
    avg_gen_tps: float
    avg_ttft: float
    total_tokens: int
    total_seconds: float
    truncated_count: int
    error_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BenchRunRequest(BaseModel):
    model: str
    prompt: str | None = None
    suite_id: str | None = None
    max_tokens: int = 4000
    temperature: float = 0.7
    system_prompt: str = ""
