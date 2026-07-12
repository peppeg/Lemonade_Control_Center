"""Bench orchestration built on the shared core completion runner."""
from __future__ import annotations

from app.models.completions import CompletionRequest
from app.services.bench.models import BenchPrompt, BenchResult, SuiteResult
from app.services.bench.suites import SUITES
from app.services.completion_runner import CompletionRunner
from app.services.hardware import get_hardware_info
from app.services.process import find_llama_server


class BenchRunner:
    def __init__(self, completion_runner: CompletionRunner, identity: dict | None = None) -> None:
        self.completion_runner = completion_runner
        self.identity = identity or {}

    async def run_prompt(self, prompt: BenchPrompt, model: str) -> BenchResult:
        before = _resource_snapshot()
        completion = await self.completion_runner.run(
            CompletionRequest(
                model=model,
                prompt=prompt.prompt,
                system_prompt=prompt.system_prompt,
                max_tokens=prompt.max_tokens,
                temperature=prompt.temperature,
                timeout_seconds=prompt.app_timeout_seconds,
                stop_sequences=prompt.stop_sequences,
            )
        )
        after = _resource_snapshot()
        return BenchResult(
            prompt_id=prompt.id,
            prompt_name=prompt.name,
            prompt=prompt.prompt,
            system_prompt=prompt.system_prompt,
            request_max_tokens=prompt.max_tokens,
            request_temperature=prompt.temperature,
            request_timeout_seconds=prompt.app_timeout_seconds,
            request_stop_sequences=prompt.stop_sequences,
            model=model,
            requested_model_name=model,
            **self.identity,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            prompt_eval_tps=completion.prompt_eval_tps,
            generation_tps=completion.generation_tps,
            ttft_seconds=completion.ttft_seconds,
            total_seconds=completion.total_seconds,
            finish_reason=completion.finish_reason,
            finish_confidence=completion.finish_confidence,
            response_preview=completion.response_text[:500],
            response_full=completion.response_text,
            reasoning_text=completion.reasoning_text,
            token_count_source=completion.token_count_source,
            completion_endpoint=completion.endpoint,
            warnings=completion.warnings,
            error=completion.error.message if completion.error else None,
            observed_backend=after.get("backend") or before.get("backend"),
            observed_ctx_size=after.get("ctx_size") or before.get("ctx_size"),
            observed_pid=after.get("pid") or before.get("pid"),
            process_rss_gb=after.get("rss_gb") or before.get("rss_gb"),
            ram_used_before_gb=before.get("ram_used_gb"),
            ram_used_after_gb=after.get("ram_used_gb"),
            swap_used_before_gb=before.get("swap_used_gb"),
            swap_used_after_gb=after.get("swap_used_gb"),
        )

    async def run_suite(self, suite_id: str, model: str) -> SuiteResult:
        suite = SUITES[suite_id]
        results = [await self.run_prompt(prompt, model) for prompt in suite.prompts]
        valid = [result for result in results if not result.error]
        avg_tps = sum(result.generation_tps for result in valid) / len(valid) if valid else 0
        avg_ttft = sum(result.ttft_seconds for result in valid) / len(valid) if valid else 0
        return SuiteResult(
            suite_id=suite.id,
            suite_name=suite.name,
            model=model,
            requested_model_name=model,
            **self.identity,
            results=results,
            avg_gen_tps=round(avg_tps, 2),
            avg_ttft=round(avg_ttft, 3),
            total_tokens=sum(result.output_tokens for result in results),
            total_seconds=round(sum(result.total_seconds for result in results), 2),
            truncated_count=sum(1 for result in results if result.finish_reason == "length"),
            error_count=sum(1 for result in results if result.error),
        )


def _resource_snapshot() -> dict:
    snapshot: dict = {}
    try:
        hardware = get_hardware_info()
        snapshot.update(ram_used_gb=hardware.ram_used_gb, swap_used_gb=hardware.swap_used_gb)
    except Exception:
        pass
    try:
        process = find_llama_server()
        if process.found and process.process:
            snapshot.update(pid=process.process.pid, rss_gb=process.process.rss_gb)
            if process.params:
                snapshot.update(backend=process.params.backend, ctx_size=process.params.ctx_size)
    except Exception:
        pass
    return snapshot
