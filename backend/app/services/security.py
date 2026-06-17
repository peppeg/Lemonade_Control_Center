"""Minimal LCC access control for LAN-safe operation."""
from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path

from starlette.requests import Request
from starlette.websockets import WebSocket

from app.config import settings

AUDIT_LOG = Path(__file__).parent.parent / "data" / "audit.jsonl"


def is_loopback_host(host: str | None) -> bool:
    """Return True for localhost/loopback client addresses."""
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def auth_required_for_host(host: str | None) -> bool:
    """Localhost is trusted unless REQUIRE_AUTH=true; LAN clients need a key."""
    return settings.require_auth or not is_loopback_host(host)


def key_configured() -> bool:
    return bool(settings.lcc_api_key)


def verify_key(value: str | None) -> bool:
    if not settings.lcc_api_key or not value:
        return False
    return hmac.compare_digest(value, settings.lcc_api_key)


def key_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-lcc-api-key") or request.query_params.get("lcc_key")


def key_from_websocket(websocket: WebSocket) -> str | None:
    auth = websocket.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return websocket.headers.get("x-lcc-api-key") or websocket.query_params.get("lcc_key")


def security_status(host: str | None, supplied_key: str | None = None) -> dict:
    required = auth_required_for_host(host)
    configured = key_configured()
    authenticated = not required or verify_key(supplied_key)
    blocked = required and not configured
    return {
        "auth_required": required,
        "authenticated": authenticated,
        "key_configured": configured,
        "lan_client": not is_loopback_host(host),
        "client_host": host,
        "blocked": blocked,
        "mode": "localhost" if is_loopback_host(host) else "lan",
    }


def audit_write(
    *,
    request: Request,
    status_code: int,
    authenticated: bool,
) -> None:
    """Append a compact audit record for mutating API requests."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return

    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "client_host": request.client.host if request.client else None,
        "authenticated": authenticated,
        "local": is_loopback_host(request.client.host if request.client else None),
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
