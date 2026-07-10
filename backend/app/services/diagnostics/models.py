"""Pydantic schemas for the diagnostic engine."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class AlertStatus(str, Enum):
    active = "active"
    resolved = "resolved"
    dismissed = "dismissed"


class DiagnosticAlert(BaseModel):
    rule_id: str
    rule_name: str
    severity: Severity
    title: str
    description: str
    impact: str
    suggestion: str
    evidence: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: AlertStatus = AlertStatus.active


class RuleResult(BaseModel):
    rule_id: str
    rule_name: str
    description: str
    passed: bool
    alert: DiagnosticAlert | None = None
    execution_time_ms: float = 0


class DiagnosticReport(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_rules: int
    passed: int
    warnings: int
    errors: int
    results: list[RuleResult]
    alerts: list[DiagnosticAlert]
    execution_time_ms: float


class AlertHistoryEntry(BaseModel):
    timestamp: datetime
    rule_id: str
    rule_name: str
    severity: Severity
    event: Literal["appeared", "resolved", "dismissed"]
    title: str
