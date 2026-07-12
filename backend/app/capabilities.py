"""
Loads and exposes capabilities detected by the M0 probe.

If probe_summary.json doesn't exist or is malformed, all capabilities
default to False (safe degradation).
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx
from pydantic import BaseModel

from app.config import settings


class Capabilities(BaseModel):
    """What the connected Lemonade instance supports."""

    # Lemonade Management API
    health: bool = False
    stats: bool = False
    system_info: bool = False
    live: bool = False
    load: bool = True      # Assumed always available
    unload: bool = True     # Assumed always available
    delete: bool = True     # Available but gated by ENABLE_DELETE
    pull: bool = True       # Available but not tested by probe

    # Internal API (require LEMONADE_ADMIN_API_KEY)
    internal_config: bool = False
    internal_set: bool = False
    internal_cleanup_cache: bool = False

    # Ollama-Compatible
    ollama_tags: bool = False
    ollama_ps: bool = False
    ollama_show: bool = False
    ollama_version: bool = False

    # OpenAI-Compatible
    openai_models: bool = False

    # WebSocket
    websocket: bool = False
    websocket_port: int | None = None

    # System commands (detected on the host)
    cmd_systemctl: bool = False
    cmd_journalctl: bool = False
    cmd_sensors: bool = False
    cmd_free: bool = False
    cmd_lemonade_cli: bool = False

    # Metadata
    lemonade_version: str | None = None
    probe_timestamp: str | None = None


# ── Mapping: probe_summary.json endpoint keys → Capabilities fields ──
_ENDPOINT_MAP: dict[str, str] = {
    "/api/v1/health": "health",
    "/api/v1/stats": "stats",
    "/api/v1/system-info": "system_info",
    "/live": "live",
    "/internal/config": "internal_config",
    "/internal/set": "internal_set",
    "/internal/cleanup-cache": "internal_cleanup_cache",
    "/api/tags": "ollama_tags",
    "/api/ps": "ollama_ps",
    "/api/show": "ollama_show",
    "/api/version": "ollama_version",
    "/api/v1/models": "openai_models",
}

_COMMAND_MAP: dict[str, str] = {
    "systemctl_status": "cmd_systemctl",
    "journalctl_recent": "cmd_journalctl",
    "sensors": "cmd_sensors",
    "free": "cmd_free",
    "lemonade_config": "cmd_lemonade_cli",
}


def load_capabilities() -> Capabilities:
    """
    Load capabilities from probe_summary.json.

    Returns a Capabilities object. If the file is missing or malformed,
    returns defaults (mostly False) — the app still works, just with
    reduced features and appropriate UI messaging.
    """
    if settings.capabilities_mode == "safe_runtime":
        return probe_safe_runtime_capabilities()

    caps = Capabilities()
    probe_path = Path(settings.capabilities_file)

    if not probe_path.exists():
        print(f"⚠ Capabilities file not found: {probe_path}")
        print("  Run 'python capabilities/probe.py' to generate it.")
        print("  Using defaults (most features disabled).")
        return caps

    try:
        with open(probe_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠ Error reading capabilities file: {e}")
        return caps

    # Metadata
    caps.lemonade_version = data.get("lemonade_version")
    caps.probe_timestamp = data.get("probe_timestamp")

    # Endpoints
    endpoints = data.get("endpoints", {})
    for endpoint_path, field_name in _ENDPOINT_MAP.items():
        endpoint_data = endpoints.get(endpoint_path, {})
        # In probe_summary, each endpoint has a "works" boolean
        works = endpoint_data.get("works", False)
        setattr(caps, field_name, works)

    # WebSocket
    ws_data = data.get("websocket", {})
    if ws_data.get("status") in ("ok", "ok_no_data"):
        caps.websocket = True
        caps.websocket_port = ws_data.get("port")

    # System commands
    commands = data.get("system_commands", {})
    for cmd_key, field_name in _COMMAND_MAP.items():
        cmd_data = commands.get(cmd_key, {})
        setattr(caps, field_name, cmd_data.get("works", False))

    return caps


def probe_safe_runtime_capabilities(client: httpx.Client | None = None) -> Capabilities:
    """Probe only non-mutating Lemonade GET endpoints for container startup."""
    caps = Capabilities(probe_timestamp=datetime.now(timezone.utc).isoformat())
    owned_client = client is None
    active_client = client or httpx.Client(timeout=2.0, trust_env=False)
    safe_endpoints = {
        "/api/v1/health": "health",
        "/api/v1/stats": "stats",
        "/api/v1/system-info": "system_info",
        "/live": "live",
        "/api/tags": "ollama_tags",
        "/api/ps": "ollama_ps",
        "/api/version": "ollama_version",
        "/api/v1/models": "openai_models",
    }
    try:
        for path, field_name in safe_endpoints.items():
            try:
                response = active_client.get(f"{settings.lemonade_url}{path}")
            except httpx.HTTPError:
                continue
            if 200 <= response.status_code < 300:
                setattr(caps, field_name, True)
                if path == "/api/v1/health":
                    try:
                        payload = response.json()
                        caps.lemonade_version = payload.get("version")
                    except (ValueError, AttributeError):
                        pass
    finally:
        if owned_client:
            active_client.close()
    return caps


# Singleton — loaded once at startup
capabilities = load_capabilities()
