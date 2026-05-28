"""Diagnostic rules for Lemonade Control Center."""
from __future__ import annotations

from app.services.diagnostics.engine import SystemState, diagnostic_rule
from app.services.diagnostics.models import DiagnosticAlert, RuleResult, Severity


def _result(
    rule_id: str,
    rule_name: str,
    severity: Severity,
    title: str,
    description: str,
    impact: str,
    suggestion: str,
    evidence: dict,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name=rule_name,
        description=description,
        passed=False,
        alert=DiagnosticAlert(
            rule_id=rule_id,
            rule_name=rule_name,
            severity=severity,
            title=title,
            description=description,
            impact=impact,
            suggestion=suggestion,
            evidence=evidence,
        ),
    )


@diagnostic_rule("timeout_mismatch", "Timeout Mismatch", "Timeout should cover estimated generation time.")
async def timeout_mismatch(state: SystemState):
    if not state.global_timeout or not state.max_tokens:
        return None
    gen_tps = state.last_gen_tps or 30
    estimated = state.max_tokens / gen_tps
    if state.global_timeout >= estimated * 1.2:
        return None
    return _result(
        "timeout_mismatch",
        "Timeout Mismatch",
        Severity.high,
        f"global_timeout {state.global_timeout}s may be too short",
        f"At about {gen_tps:.1f} tokens/s, {state.max_tokens} tokens need about {estimated:.0f}s.",
        "Generation can be cut off before completion.",
        f"Increase global_timeout to at least {int(estimated * 1.2)}s or reduce max_tokens.",
        {"global_timeout": state.global_timeout, "max_tokens": state.max_tokens, "gen_tps": gen_tps},
    )


@diagnostic_rule("truncation_confirmed", "Truncation Confirmed", "Detects confirmed finish_reason=length.")
async def truncation_confirmed(state: SystemState):
    if state.last_finish_reason != "length" or state.last_finish_confidence != "confirmed":
        return None
    return _result(
        "truncation_confirmed",
        "Truncation Confirmed",
        Severity.high,
        "Last output was truncated",
        "The last task ended with finish_reason=length.",
        "The generated response is incomplete.",
        "Increase max_tokens or reduce prompt length.",
        {"output_tokens": state.last_output_tokens, "confidence": state.last_finish_confidence},
    )


@diagnostic_rule("truncation_inferred", "Truncation Inferred", "Detects probable truncation from token limits.")
async def truncation_inferred(state: SystemState):
    if state.last_finish_reason != "length" or state.last_finish_confidence != "inferred":
        return None
    return _result(
        "truncation_inferred",
        "Truncation Inferred",
        Severity.medium,
        "Last output probably hit max_tokens",
        "The parser inferred truncation from output token count.",
        "The response may be incomplete.",
        "Increase max_tokens if the answer was cut short.",
        {"output_tokens": state.last_output_tokens, "max_tokens": state.max_tokens},
    )


@diagnostic_rule("swap_risk", "Swap Risk", "Checks model plus KV cache against available RAM.")
async def swap_risk(state: SystemState):
    if not state.loaded_model or not state.model_size_gb:
        return None
    ctx = state.ctx_size or 8192
    kv_gb = (ctx / 8192) * (1.5 if state.model_size_gb > 60 else 1.0)
    total = state.model_size_gb + kv_gb
    if total < state.ram_available_gb * 0.95:
        return None
    return _result(
        "swap_risk",
        "Swap Risk",
        Severity.high,
        "Loaded model may exceed RAM headroom",
        f"Model plus estimated KV cache needs about {total:.1f} GB; available RAM is {state.ram_available_gb:.1f} GB.",
        "The system can fall back to swap with severe slowdown.",
        "Reduce ctx_size, unload other workloads, or use a smaller model.",
        {"model_gb": state.model_size_gb, "kv_estimate_gb": kv_gb, "ram_available_gb": state.ram_available_gb},
    )


@diagnostic_rule("context_headroom", "Context Headroom", "Checks ctx_size minus max_tokens.")
async def context_headroom(state: SystemState):
    if not state.ctx_size or not state.max_tokens:
        return None
    headroom = state.ctx_size - state.max_tokens
    if headroom >= 2000:
        return None
    return _result(
        "context_headroom",
        "Context Headroom",
        Severity.medium,
        "Low context headroom",
        f"ctx_size - max_tokens leaves only {headroom} tokens for prompt and history.",
        "Long prompts may be truncated.",
        "Increase ctx_size or reduce max_tokens.",
        {"ctx_size": state.ctx_size, "max_tokens": state.max_tokens, "headroom": headroom},
    )


@diagnostic_rule("capability_gap", "Capability Gap", "Checks admin capability availability.")
async def capability_gap(state: SystemState):
    if state.has_admin_key and state.has_internal_config and state.has_internal_set:
        return None
    return _result(
        "capability_gap",
        "Capability Gap",
        Severity.info,
        "Admin config endpoints are not fully available",
        "LCC cannot read or write every Lemonade internal config endpoint.",
        "Runtime config and profile apply may be partial.",
        "Set LEMONADE_ADMIN_API_KEY and re-run the capability probe.",
        {
            "has_admin_key": state.has_admin_key,
            "internal_config": state.has_internal_config,
            "internal_set": state.has_internal_set,
        },
    )


@diagnostic_rule("idle_heavy", "Idle Heavy", "Detects a long-running loaded model with no recent task.")
async def idle_heavy(state: SystemState):
    if not state.loaded_model or state.llama_uptime_s < 3600 or state.last_task_available:
        return None
    return _result(
        "idle_heavy",
        "Idle Heavy",
        Severity.low,
        "Large model appears idle",
        f"{state.loaded_model} has been loaded for {state.llama_uptime_s / 3600:.1f}h without recent task stats.",
        "RAM remains occupied while the model is idle.",
        "Unload the model if you do not need it ready.",
        {"model": state.loaded_model, "rss_gb": state.llama_rss_gb, "uptime_seconds": state.llama_uptime_s},
    )


@diagnostic_rule("no_mmap", "No-mmap Mode", "Informs when mmap is disabled.")
async def no_mmap(state: SystemState):
    if state.llama_mmap is None or state.llama_mmap:
        return None
    return _result(
        "no_mmap",
        "No-mmap Mode",
        Severity.info,
        "llama-server runs with mmap disabled",
        "The full model is loaded into RAM instead of memory mapped.",
        "Startup and RSS behavior are different from mmap mode.",
        "This is acceptable for dedicated machines; verify it is intentional.",
        {"mmap": state.llama_mmap, "rss_gb": state.llama_rss_gb},
    )


@diagnostic_rule("high_ram", "High RAM Usage", "Warns when RAM exceeds 90%.")
async def high_ram(state: SystemState):
    if state.ram_percent < 90:
        return None
    severity = Severity.critical if state.ram_percent >= 95 else Severity.high
    return _result(
        "high_ram",
        "High RAM Usage",
        severity,
        f"RAM usage is {state.ram_percent:.0f}%",
        f"Only {state.ram_available_gb:.1f} GB RAM is available.",
        "The system may swap or become unstable.",
        "Unload models, reduce ctx_size, or close other workloads.",
        {"ram_percent": state.ram_percent, "ram_available_gb": state.ram_available_gb},
    )


@diagnostic_rule("disk_pressure", "Disk Pressure", "Warns when disk free space is low.")
async def disk_pressure(state: SystemState):
    if state.disk_free_gb > 20:
        return None
    severity = Severity.high if state.disk_free_gb <= 5 else Severity.medium
    return _result(
        "disk_pressure",
        "Disk Pressure",
        severity,
        f"Only {state.disk_free_gb:.1f} GB free on disk",
        "Disk space is low for model storage and logs.",
        "Model pulls can fail and logs can fill remaining space.",
        "Delete unused models or free disk space.",
        {"disk_free_gb": state.disk_free_gb, "disk_percent": state.disk_percent},
    )


@diagnostic_rule("slow_generation", "Slow Generation", "Detects generation below 10 tokens/s.")
async def slow_generation(state: SystemState):
    if not state.last_gen_tps or state.last_gen_tps > 10:
        return None
    return _result(
        "slow_generation",
        "Slow Generation",
        Severity.medium,
        f"Generation speed is {state.last_gen_tps:.1f} tokens/s",
        "The last completed task was slower than the expected local-interactive threshold.",
        "Responses will feel slow and may indicate swap or wrong backend.",
        "Check RAM pressure, backend selection, and ctx_size.",
        {"generation_tps": state.last_gen_tps, "backend": state.llamacpp_backend, "ram_percent": state.ram_percent},
    )


@diagnostic_rule("no_model", "No Model Loaded", "Checks if Lemonade is healthy but idle.")
async def no_model(state: SystemState):
    if not state.server_healthy or state.loaded_model:
        return None
    return _result(
        "no_model",
        "No Model Loaded",
        Severity.low,
        "Lemonade is running without a loaded model",
        "The server is reachable, but no model is currently loaded.",
        "Inference requests can fail until a model is loaded.",
        "Load a model from the Models page.",
        {"server_healthy": state.server_healthy, "loaded_model": state.loaded_model},
    )
