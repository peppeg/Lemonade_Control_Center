"""
Diagnostic bundle generator.

Collects all available data into a single ZIP file for troubleshooting.
"""
import asyncio
import io
import json
import platform
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import settings
from app.capabilities import capabilities
from app.dependencies import get_provider
from app.services.hardware import get_hardware_info, get_temperatures
from app.services.process import find_llama_server, get_service_status
from app.services.log_parser import get_recent_logs, parse_last_task

router = APIRouter(prefix="/api", tags=["diagnostic"])


@router.get("/diagnostic-bundle")
async def generate_diagnostic_bundle():
    """Generate a diagnostic ZIP bundle with all available system info."""
    provider = get_provider()
    bundle: dict[str, str] = {}
    errors: dict[str, str] = {}

    async def _safe_collect(name: str, coro):
        try:
            result = await coro
            if hasattr(result, "model_dump"):
                bundle[name] = json.dumps(result.model_dump(), indent=2, default=str)
            else:
                bundle[name] = json.dumps(result, indent=2, default=str)
        except Exception as e:
            errors[name] = str(e)

    def _safe_collect_sync(name: str, func):
        try:
            result = func()
            if hasattr(result, "model_dump"):
                bundle[name] = json.dumps(result.model_dump(), indent=2, default=str)
            else:
                bundle[name] = json.dumps(result, indent=2, default=str)
        except Exception as e:
            errors[name] = str(e)

    await asyncio.gather(
        _safe_collect("health.json", provider.get_health()),
        _safe_collect("stats.json", provider.get_stats()),
        _safe_collect("models.json", provider.list_models()),
        _safe_collect("running_models.json", provider.get_running_models()),
        return_exceptions=True
    )

    try:
        config = await provider.get_config()
        bundle["config.json"] = json.dumps(config.model_dump(), indent=2, default=str)
    except Exception as e:
        errors["config.json"] = str(e)

    _safe_collect_sync("hardware.json", get_hardware_info)
    _safe_collect_sync("temperatures.json", get_temperatures)
    _safe_collect_sync("llama_server.json", find_llama_server)
    _safe_collect_sync("service_status.json", get_service_status)
    _safe_collect_sync("last_task.json", parse_last_task)

    try:
        logs = get_recent_logs(n_lines=500)
        bundle["last_logs.txt"] = "\n".join(
            entry.raw for entry in logs.entries
        )
    except Exception as e:
        errors["last_logs.txt"] = str(e)

    bundle["capabilities.json"] = json.dumps(
        capabilities.model_dump(), indent=2, default=str
    )

    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "lemonade_url": settings.lemonade_url,
        "lemonade_version": capabilities.lemonade_version,
        "probe_timestamp": capabilities.probe_timestamp,
        "os": platform.platform(),
        "python": platform.python_version(),
        "errors": errors,
    }
    bundle["meta.json"] = json.dumps(meta, indent=2, default=str)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
    filename = f"lcc-diagnostic-{timestamp}.zip"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in bundle.items():
            zf.writestr(name, content)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
