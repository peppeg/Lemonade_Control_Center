"""Static frontend serving for the unified LCC runtime."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(include_in_schema=False)


def _frontend_root() -> Path:
    return Path(settings.frontend_build_dir).expanduser().resolve()


def frontend_available() -> bool:
    root = _frontend_root()
    return root.is_dir() and (root / "index.html").is_file()


def _resolve_static_path(path: str) -> Path | None:
    root = _frontend_root()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


@router.api_route("/", methods=["GET", "HEAD"])
async def frontend_index():
    if not frontend_available():
        raise HTTPException(
            status_code=503,
            detail="Frontend build not found. Run `npm run build` in frontend or set SERVE_FRONTEND=false.",
        )
    return FileResponse(_frontend_root() / "index.html")


@router.api_route("/{path:path}", methods=["GET", "HEAD"])
async def frontend_fallback(path: str):
    if path.startswith(("api/", "ws/")):
        raise HTTPException(status_code=404, detail="Not found")
    if not frontend_available():
        raise HTTPException(
            status_code=503,
            detail="Frontend build not found. Run `npm run build` in frontend or set SERVE_FRONTEND=false.",
        )

    static_file = _resolve_static_path(path)
    if static_file is not None:
        return FileResponse(static_file)

    return FileResponse(_frontend_root() / "index.html")
