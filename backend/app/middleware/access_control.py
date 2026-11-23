"""LAN-safe access control middleware for LCC API routes."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.services.security import (
    audit_write,
    evaluate_access,
    key_from_connection,
)

PUBLIC_API_PATHS = {
    "/api/security/status",
}


class LccAccessControlMiddleware(BaseHTTPMiddleware):
    """Require LCC_API_KEY for non-loopback API clients.

    Static/frontend routes remain public so the browser can render the login
    prompt. API routes are protected whenever the request is remote or
    REQUIRE_AUTH=true.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or path in PUBLIC_API_PATHS:
            return await call_next(request)

        host = request.client.host if request.client else None
        access = evaluate_access(host, key_from_connection(request))

        if access.blocked:
            response = JSONResponse(
                {
                    "detail": (
                        "LAN/API access is blocked because LCC_API_KEY is not configured. "
                        "Set LCC_API_KEY or bind the app to 127.0.0.1."
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
