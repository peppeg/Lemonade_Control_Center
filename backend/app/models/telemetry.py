"""Typed telemetry contracts shared by providers, evidence, and API responses."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

TelemetryQuality = Literal["measured", "inferred", "unavailable", "unsupported", "degraded"]


class TelemetryMetric(BaseModel):
    name: str
    value: float | int | str | None = None
    unit: str | None = None
    quality: TelemetryQuality
    provider_id: str
    device: str | None = None
    evidence: str = ""


class TelemetrySample(BaseModel):
    provider_id: str
    provider_label: str
    phase: Literal["point", "start", "end"] = "point"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quality: TelemetryQuality
    available: bool = False
    metrics: list[TelemetryMetric] = Field(default_factory=list)
    error: str | None = None


class TelemetrySnapshot(BaseModel):
    samples: list[TelemetrySample] = Field(default_factory=list)
    accelerator_ownership: Literal["unproven"] = "unproven"
    ownership_note: str = (
        "Provider activity is correlated by time only; it does not prove that Lemonade or llama-server owned accelerator work."
    )
