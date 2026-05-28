"""Diagnostic endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.diagnostics.engine import DiagnosticEngine
from app.services.diagnostics.history import AlertHistory
from app.services.diagnostics.models import DiagnosticReport

import app.services.diagnostics.rules  # noqa: F401

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

engine = DiagnosticEngine()
history = AlertHistory()


@router.get("", response_model=DiagnosticReport)
async def run_diagnostics():
    report = await engine.run()
    return history.record(report)


@router.get("/history")
async def get_history(limit: int = Query(default=50, ge=1, le=200)):
    return {"entries": history.get_entries(limit)}


@router.post("/dismiss")
async def dismiss_alert(rule_id: str):
    history.dismiss(rule_id)
    return {"dismissed": rule_id}
