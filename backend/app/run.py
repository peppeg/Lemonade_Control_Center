"""Run Lemonade Control Center as a single-process local application."""
from __future__ import annotations

import uvicorn

from app.config import settings


def main() -> None:
    if settings.lan_mode:
        if settings.app_host in {"127.0.0.1", "localhost", "::1"}:
            raise SystemExit("LAN_MODE=true requires APP_HOST=0.0.0.0 or an explicit LAN address.")
        if not settings.require_auth:
            raise SystemExit("LAN_MODE=true requires REQUIRE_AUTH=true.")

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
