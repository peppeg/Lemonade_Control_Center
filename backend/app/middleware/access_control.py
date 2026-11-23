"""LAN-safe access control middleware for LCC API routes."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.services.security import (
    audit_write,
    connection_access,
    cross_site_request,
)

PUBLIC_API_PATHS = {
    "/api/security/status",
}


class LccAccessControlMiddleware(BaseHTTPMiddleware):
    """Require LCC_API_KEY for API clients that are not directly on this host.

    Static/frontend routes remain public so the browser can render the login
    prompt. API routes are protected whenever the request is remote, forwarded
    by a proxy, sent to an unknown host name, or REQUIRE_AUTH=true. State-changing requests from other web sites are refused
    on every path, whatever the client address or key.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if cross_site_request(request):
            response = JSONResponse(
                {
                    "detail": (
                        "Cross-site request refused. If LCC runs behind a reverse proxy, "
                        "add its address to ALLOWED_ORIGINS."
                    )
                },
                status_code=403,
            )
            audit_write(request=request, status_code=response.status_code, authenticated=False)
            return response

        path = request.url.path
        if not path.startswith("/api/") or path in PUBLIC_API_PATHS:
            return await call_next(request)

        access = connection_access(request)

        if access.blocked:
            response = JSONResponse(
                {
                    "detail": (
                        "LAN/API access is blocked because LCC_API_KEY is not configured. "
                        "Set LCC_API_KEY, or open LCC directly on its own host as localhost."
                    )
                },
                status_code=503,
            )
            audit_write(request=request, status_code=response.status_code, authenticated=False)
            return response

        if not access.authenticated:
            response = JSONResponse({"detail": "LCC API key required."}, status_code=401)
            audit_write(request=request, status_code=response.status_code, authenticated=False)
            return response

        response = await call_next(request)
        audit_write(request=request, status_code=response.status_code, authenticated=access.authenticated)
        return response
