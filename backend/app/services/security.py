"""Minimal LCC access control for LAN-safe operation."""
from __future__ import annotations

import hmac
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from starlette.requests import HTTPConnection, Request
from starlette.websockets import WebSocket

from app.config import settings

logger = logging.getLogger(__name__)

AUDIT_LOG = Path(__file__).parent.parent / "data" / "audit.jsonl"

# Origins of the frontend development servers.
DEV_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
)

# Methods that change state: audited, and refused when they come from another site.
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Headers a proxy adds to name the client it speaks for.
FORWARDING_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip")

_DEFAULT_PORTS = {"http": 80, "https": 443}
_warned_about_forwarding = False


@dataclass(frozen=True)
class AccessDecision:
    """Outcome of the key rules for one client."""

    auth_required: bool
    authenticated: bool
    # A key is required but none is configured, so no client can supply it.
    blocked: bool


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


def auth_required_for_host(host: str | None, *, forwarded: bool = False) -> bool:
    """Localhost is trusted unless REQUIRE_AUTH=true; other clients need a key.

    Localhost trust covers direct connections only. A forwarded request comes
    from whoever the proxy speaks for, and the headers that name that client
    may be the client's own, so no forwarded address is ever trusted as local.
    """
    return settings.require_auth or forwarded or not is_loopback_host(host)


def client_host(connection: HTTPConnection) -> str | None:
    return connection.client.host if connection.client else None


def forwarded_by_proxy(connection: HTTPConnection) -> bool:
    return any(header in connection.headers for header in FORWARDING_HEADERS)


def key_configured() -> bool:
    return bool(settings.lcc_api_key)


def verify_key(value: str | None) -> bool:
    if not settings.lcc_api_key or not value:
        return False
    return hmac.compare_digest(value, settings.lcc_api_key)


def key_from_connection(connection: HTTPConnection) -> str | None:
    """Read the LCC key from an HTTP request or a WebSocket handshake."""
    auth = connection.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return connection.headers.get("x-lcc-api-key") or connection.query_params.get("lcc_key")


def connection_access(connection: HTTPConnection) -> AccessDecision:
    """Apply the key rules. HTTP and WebSocket clients share this decision."""
    forwarded = forwarded_by_proxy(connection)
    if forwarded:
        _warn_about_forwarding()
    return evaluate_access(
        client_host(connection), key_from_connection(connection), forwarded=forwarded
    )


def _warn_about_forwarding() -> None:
    """Explain once why a proxied setup asks for a key."""
    global _warned_about_forwarding
    if _warned_about_forwarding or settings.require_auth or settings.trusted_proxy_ips.strip():
        return
    _warned_about_forwarding = True
    logger.warning(
        "A request was forwarded by a proxy. Forwarded clients always need LCC_API_KEY. "
        "Set TRUSTED_PROXY_IPS to the proxy address to record the real client address."
    )


def evaluate_access(
    host: str | None, supplied_key: str | None, *, forwarded: bool = False
) -> AccessDecision:
    required = auth_required_for_host(host, forwarded=forwarded)
    return AccessDecision(
        auth_required=required,
        authenticated=not required or verify_key(supplied_key),
        blocked=required and not key_configured(),
    )


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Return True when a browser Origin belongs to this LCC instance.

    A missing Origin is accepted because non-browser clients do not send one.
    Schemes are not compared with the request: a TLS proxy serves https to the
    browser while LCC sees http.
    """
    if origin is None or _origin_configured(origin):
        return True
    parsed = _parse_origin(origin)
    if parsed is None:
        return False
    scheme, name, port = parsed
    return _parse_host(host, _DEFAULT_PORTS[scheme]) == (name, port)


def cross_site_request(request: Request) -> bool:
    """Return True for a state-changing request sent by another web site.

    Localhost is trusted without a key, so a page open in a browser on this host
    could otherwise send body-less POST requests that need no CORS preflight.

    Browsers set Sec-Fetch-Site themselves and pages cannot forge it, so it is
    authoritative when present; this also keeps proxies that rewrite Host
    working. Without it (older browsers, plain-http LAN access) the Origin
    decides. Non-browser clients send neither header and are not affected.
    """
    if request.method not in MUTATING_METHODS:
        return False
    origins = request.headers.getlist("origin")
    if origins and all(_origin_configured(origin) for origin in origins):
        return False
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site not in {"same-origin", "none"}
    host = request.headers.get("host")
    return not all(origin_allowed(origin, host) for origin in origins)


def _origin_configured(origin: str) -> bool:
    parsed = _parse_origin(origin)
    return parsed is not None and any(
        parsed == _parse_origin(item) for item in (*DEV_ORIGINS, *_configured_origins())
    )


def _configured_origins() -> list[str]:
    return [item.strip() for item in settings.allowed_origins.split(",") if item.strip()]


def _parse_origin(value: str) -> tuple[str, str, int] | None:
    """Split an origin into scheme, host and port, or None when it is not one."""
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in _DEFAULT_PORTS or not parts.hostname or "@" in parts.netloc:
        return None
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        return None
    return parts.scheme, parts.hostname, _DEFAULT_PORTS[parts.scheme] if port is None else port


def _parse_host(value: str | None, default_port: int) -> tuple[str, int] | None:
    if not value:
        return None
    try:
        parts = urlsplit(f"//{value.strip()}")
        port = parts.port
    except ValueError:
        return None
    if not parts.hostname or "@" in parts.netloc or parts.path:
        return None
    return parts.hostname, default_port if port is None else port


async def authorize_websocket(websocket: WebSocket) -> bool:
    """Check a WebSocket handshake, closing it when it is refused.

    Every WebSocket route must call this before accept(). HTTP middleware never
    sees WebSocket scopes, and browsers do not apply CORS to WebSockets, so the
    Origin check is what keeps other sites from opening these sockets.
    """
    host_header = websocket.headers.get("host")
    origins = websocket.headers.getlist("origin")
    if (
        all(origin_allowed(origin, host_header) for origin in origins)
        and connection_access(websocket).authenticated
    ):
        return True
    await websocket.close(code=1008)
    return False


def security_status(
    host: str | None, supplied_key: str | None = None, *, forwarded: bool = False
) -> dict:
    access = evaluate_access(host, supplied_key, forwarded=forwarded)
    local = is_loopback_host(host) and not forwarded
    return {
        "auth_required": access.auth_required,
        "authenticated": access.authenticated,
        "key_configured": key_configured(),
        "lan_client": not local,
        "client_host": host,
        "blocked": access.blocked,
        "mode": "localhost" if local else "lan",
    }


def audit_write(
    *,
    request: Request,
    status_code: int,
    authenticated: bool,
) -> None:
    """Append a compact audit record for mutating API requests."""
    if request.method not in MUTATING_METHODS:
        return

    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "client_host": client_host(request),
        "authenticated": authenticated,
        "local": is_loopback_host(client_host(request)) and not forwarded_by_proxy(request),
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
