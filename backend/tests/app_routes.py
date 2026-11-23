"""List the app's routes on every supported FastAPI version."""
import re

from fastapi.routing import APIWebSocketRoute

from app.main import app

try:
    # Newer FastAPI keeps included routers nested instead of flattening app.routes.
    from fastapi.routing import iter_route_contexts
except ImportError:

    def iter_route_contexts(routes):
        return iter(routes)


def websocket_paths() -> list[str]:
    return [
        _concrete(route.path)
        for route in iter_route_contexts(app.routes)
        if isinstance(getattr(route, "original_route", route), APIWebSocketRoute)
    ]


def http_routes() -> list[tuple[str, str]]:
    """Return (method, path) pairs."""
    return sorted(
        (method, _concrete(route.path))
        for route in iter_route_contexts(app.routes)
        for method in (getattr(route, "methods", None) or ())
    )


def _concrete(path: str) -> str:
    """Fill path parameters with a placeholder."""
    return re.sub(r"\{[^}]+\}", "x", path)
