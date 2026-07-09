"""Diagnostic bundle download endpoint."""
from __future__ import annotations

import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.diagnostic_bundle import DiagnosticBundleBuilder

router = APIRouter(prefix="/api", tags=["diagnostic"])


@router.get("/diagnostic-bundle")
async def generate_diagnostic_bundle():
    """Generate a sanitized diagnostic ZIP bundle with available system info."""
    content, filename = await DiagnosticBundleBuilder().build()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
