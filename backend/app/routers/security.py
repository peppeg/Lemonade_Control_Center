"""LCC access-control status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.security import (
    client_host,
    forwarded_by_proxy,
    key_from_connection,
    security_status,
)

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/status")
async def get_security_status(request: Request):
    return security_status(
        client_host(request),
        key_from_connection(request),
        forwarded=forwarded_by_proxy(request),
    )
