"""Contracts for guided Hugging Face repository intake."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Applicability = Literal["applicable", "possible", "unsupported", "unavailable"]
MemoryRisk = Literal["low", "moderate", "high", "unknown"]


class IntakeInspectRequest(BaseModel):
    repo_id: str

    @field_validator("repo_id")
    @classmethod
    def validate_repo_id(cls, value: str) -> str:
        normalized = value.strip().removeprefix("https://huggingface.co/").strip("/")
        if normalized.count("/") != 1 or any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("Use a Hugging Face repository id in owner/repository form.")
        return normalized


class IntakeSearchRequest(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Enter at least two characters.")
        return normalized


class IntakeSearchResult(BaseModel):
    repo_id: str
    downloads: int | None = None
    gated: bool | str | None = None
    last_modified: str | None = None
    tags: list[str] = Field(default_factory=list)


class IntakeSearchResponse(BaseModel):
    query: str
    results: list[IntakeSearchResult] = Field(default_factory=list)
    note: str = "A maximum of five GGUF repository candidates is shown; results are discovery aids, not model recommendations."


class IntakeVariant(BaseModel):
    name: str
    format: Literal["gguf", "onnx"]
    primary_file: str
    files: list[str] = Field(default_factory=list)
    sharded: bool = False
    size_bytes: int | None = None
    estimated_runtime_gb: float | None = None
    memory_risk: MemoryRisk = "unknown"
    fits_available_ram: bool | None = None
    estimate_note: str


class FormatAssessment(BaseModel):
    format: Literal["gguf", "onnx"]
    applicability: Applicability
    recipe: str | None = None
    evidence: str


class IntakeReport(BaseModel):
    repo_id: str
    suggested_model_name: str
    suggested_labels: list[str] = Field(default_factory=list)
    mmproj_files: list[str] = Field(default_factory=list)
    formats: list[FormatAssessment] = Field(default_factory=list)
    variants: list[IntakeVariant] = Field(default_factory=list)
    ram_total_gb: float
    ram_available_gb: float
    recommended_variant: str | None = None
    warnings: list[str] = Field(default_factory=list)
    inspection_sources: list[str] = Field(default_factory=list)
    ownership_note: str = "LCC inspects and profiles; Lemonade owns model registration, download, import, and updates."


class IntakeProfileRequest(BaseModel):
    repo_id: str
    model_name: str
    variant_name: str
    variant_size_bytes: int | None = None
    profile_name: str = "Hugging Face Intake"
    intent: str = "Agent Fallback"
    runtime_id: str | None = None


class IntakePullRequest(BaseModel):
    model_name: str
    checkpoint: str
    recipe: str
    reasoning: bool = False
    vision: bool = False
    embedding: bool = False
    reranking: bool = False
    mmproj: str | None = None

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("user.") or len(normalized) <= len("user."):
            raise ValueError("Custom Lemonade model names must use the user. namespace.")
        return normalized


class IntakeProfileResponse(BaseModel):
    model_name: str
    profile_id: str
    profile_name: str
