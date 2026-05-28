"""System state collector for diagnostics."""
from __future__ import annotations

import psutil

from app.capabilities import capabilities
from app.config import settings
from app.models.schemas import FinishReasonConfidence
from app.providers.lemonade import LemonadeProvider
from app.services.diagnostics.engine import SystemState
from app.services.log_parser import parse_last_task
from app.services.process import find_llama_server


async def collect_full_state() -> SystemState:
    state = SystemState()
    provider = LemonadeProvider()

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    state.ram_total_gb = memory.total / (1024**3)
    state.ram_available_gb = memory.available / (1024**3)
    state.ram_percent = memory.percent
    state.cpu_percent = psutil.cpu_percent(interval=0.1)
    state.disk_percent = disk.percent
    state.disk_free_gb = disk.free / (1024**3)
    state.has_admin_key = bool(settings.lemonade_admin_api_key)
    state.has_internal_config = capabilities.internal_config
    state.has_internal_set = capabilities.internal_set

    try:
        health = await provider.get_health()
        state.server_healthy = health.status in {"ok", "running"}
        state.server_version = health.version
    except Exception:
        state.server_healthy = False

    try:
        running = await provider.get_running_models()
        if running.models:
            model = running.models[0]
            state.loaded_model = model.name
            if model.size:
                state.model_size_gb = model.size / (1024**3)
    except Exception:
        pass

    try:
        config = await provider.get_config()
        raw = config.raw
        state.ctx_size = _int(raw.get("ctx_size") or raw.get("context_size"))
        state.global_timeout = _int(raw.get("global_timeout"))
        state.llamacpp_backend = _str(raw.get("llamacpp_backend") or raw.get("backend"))
        state.max_tokens = _int(raw.get("max_tokens"))
        state.temperature = _float(raw.get("temperature"))
    except Exception:
        pass

    try:
        info = find_llama_server()
        if info.found and info.process:
            state.llama_pid = info.process.pid
            state.llama_rss_gb = info.process.rss_gb
            state.llama_cpu = info.process.cpu_percent
            state.llama_uptime_s = info.process.uptime_seconds or 0
            if info.params:
                state.ctx_size = state.ctx_size or info.params.ctx_size
                state.llamacpp_backend = state.llamacpp_backend or info.params.backend
                state.llama_mmap = info.params.mmap
                state.llama_ngl = info.params.ngl
    except Exception:
        pass

    try:
        if capabilities.cmd_journalctl:
            task = parse_last_task(configured_max_tokens=state.max_tokens)
            if task.available:
                state.last_task_available = True
                state.last_input_tokens = task.input_tokens
                state.last_output_tokens = task.output_tokens
                state.last_gen_tps = task.generation_tps
                state.last_prompt_tps = task.prompt_eval_tps
                state.last_finish_reason = task.finish_reason.reason
                confidence = task.finish_reason.confidence
                state.last_finish_confidence = (
                    confidence.value if isinstance(confidence, FinishReasonConfidence) else str(confidence)
                )
    except Exception:
        pass

    return state


def _int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _str(value: object) -> str | None:
    return str(value) if value is not None else None
