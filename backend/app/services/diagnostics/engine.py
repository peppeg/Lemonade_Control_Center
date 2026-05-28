"""Diagnostic engine and rule registry."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from app.services.diagnostics.models import (
    DiagnosticAlert,
    DiagnosticReport,
    RuleResult,
    Severity,
)


class SystemState:
    def __init__(self) -> None:
        self.server_healthy = False
        self.server_version: str | None = None
        self.loaded_model: str | None = None
        self.model_size_gb: float | None = None
        self.ctx_size: int | None = None
        self.global_timeout: int | None = None
        self.llamacpp_backend: str | None = None
        self.ram_total_gb = 0.0
        self.ram_available_gb = 0.0
        self.ram_percent = 0.0
        self.cpu_percent = 0.0
        self.disk_percent = 0.0
        self.disk_free_gb = 0.0
        self.llama_pid: int | None = None
        self.llama_rss_gb = 0.0
        self.llama_cpu = 0.0
        self.llama_uptime_s = 0.0
        self.llama_mmap: bool | None = None
        self.llama_ngl: int | None = None
        self.last_task_available = False
        self.last_input_tokens: int | None = None
        self.last_output_tokens: int | None = None
        self.last_gen_tps: float | None = None
        self.last_prompt_tps: float | None = None
        self.last_finish_reason: str | None = None
        self.last_finish_confidence: str | None = None
        self.max_tokens: int | None = None
        self.temperature: float | None = None
        self.has_internal_config = False
        self.has_internal_set = False
        self.has_admin_key = False


RuleFunc = Callable[[SystemState], Awaitable[RuleResult | None]]
_rules: list[tuple[str, str, str, RuleFunc]] = []


def diagnostic_rule(rule_id: str, name: str, description: str = ""):
    def decorator(func: RuleFunc):
        _rules.append((rule_id, name, description, func))
        return func

    return decorator


class DiagnosticEngine:
    async def collect_state(self) -> SystemState:
        from app.services.diagnostics.collectors import collect_full_state

        return await collect_full_state()

    async def run(self, state: SystemState | None = None) -> DiagnosticReport:
        start = time.monotonic()
        if state is None:
            state = await self.collect_state()

        results: list[RuleResult] = []
        alerts: list[DiagnosticAlert] = []

        for rule_id, name, description, func in _rules:
            rule_start = time.monotonic()
            try:
                result = await func(state)
                if result is None:
                    result = RuleResult(
                        rule_id=rule_id,
                        rule_name=name,
                        description=description,
                        passed=True,
                    )
                result.execution_time_ms = (time.monotonic() - rule_start) * 1000
                results.append(result)
                if result.alert is not None:
                    alerts.append(result.alert)
            except Exception as exc:
                results.append(
                    RuleResult(
                        rule_id=rule_id,
                        rule_name=name,
                        description=f"Rule error: {exc}",
                        passed=True,
                        execution_time_ms=(time.monotonic() - rule_start) * 1000,
                    )
                )

        return DiagnosticReport(
            total_rules=len(results),
            passed=sum(1 for result in results if result.passed),
            warnings=sum(1 for alert in alerts if alert.severity in {Severity.medium, Severity.high}),
            errors=sum(1 for alert in alerts if alert.severity == Severity.critical),
            results=results,
            alerts=alerts,
            execution_time_ms=(time.monotonic() - start) * 1000,
        )
