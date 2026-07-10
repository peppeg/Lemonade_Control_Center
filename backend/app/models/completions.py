"""Core contracts for LCC-owned OpenAI-compatible completion requests."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CompletionErrorKind = Literal["connection", "timeout", "http", "protocol", "empty_response"]
MetricSource = Literal["api", "estimated", "mixed", "unavailable"]


class CompletionRequest(BaseModel):
    model: str
    prompt: str
    system_prompt: str = ""
    max_tokens: int = Field(default=4000, ge=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    stop_sequences: list[str] = Field(default_factory=list)


class CompletionError(BaseModel):
    kind: CompletionErrorKind
    message: str
    status_code: int | None = None
    endpoint: str | None = None


class CompletionResult(BaseModel):
    model: str
    response_text: str = ""
    reasoning_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    token_count_source: MetricSource = "unavailable"
    prompt_eval_tps: float = 0
    generation_tps: float = 0
    ttft_seconds: float = 0
    total_seconds: float = 0
    finish_reason: str = "unknown"
    finish_confidence: str = "unknown"
    endpoint: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: CompletionError | None = None

    @property
    def success(self) -> bool:
        return self.error is None
