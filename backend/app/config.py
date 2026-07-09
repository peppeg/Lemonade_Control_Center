"""
Application settings loaded from environment variables and .env file.

Hierarchy (highest priority first):
  1. Environment variables
  2. .env file
  3. Defaults defined here
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Lemonade Server ──
    lemonade_url: str = "http://localhost:13305"
    lemonade_admin_api_key: str | None = None
    lemonade_recipe_options_file: str = "/opt/var/lib/lemonade/.cache/lemonade/recipe_options.json"

    # ── Safety Flags ──
    enable_delete: bool = False
    enable_restart: bool = False
    enable_bench_lab: bool = False

    # ── LCC Access Control ──
    # Localhost remains trusted by default. Non-loopback API access requires
    # this key, and REQUIRE_AUTH can force the same behavior on localhost.
    lcc_api_key: str | None = None
    require_auth: bool = False

    # ── Server ──
    app_host: str = "127.0.0.1"
    app_port: int = 17600
    serve_frontend: bool = True
    frontend_build_dir: str = str(Path(__file__).parent.parent.parent / "frontend" / "build")
    lan_mode: bool = False

    # Legacy backend-dev defaults retained for external scripts that may still
    # read HOST/PORT. The product runtime uses APP_HOST/APP_PORT above.
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # ── Capabilities ──
    # Path al probe_summary.json generato da M0
    capabilities_file: str = str(
        Path(__file__).parent.parent.parent / "capabilities" / "results" / "probe_summary.json"
    )

    # ── App Info ──
    app_name: str = "Lemonade Control Center"
    app_version: str = "0.2.0"


# Singleton
settings = Settings()
