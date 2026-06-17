"""LCC access-control status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.security import key_from_request, security_status

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/status")
async def get_security_status(request: Request):
    host = request.client.host if request.client else None
    return security_status(host, key_from_request(request))
