"""Bench runner for Lemonade OpenAI-compatible chat completions."""
from __future__ import annotations

import json
import time

import httpx

from app.config import settings
from app.services.bench.models import BenchPrompt, BenchResult, SuiteResult
from app.services.bench.suites import SUITES


class BenchRunner:
    def __init__(self) -> None:
        self.base_url = settings.lemonade_url.rstrip("/")

    async def run_prompt(self, prompt: BenchPrompt, model: str) -> BenchResult:
        start = time.monotonic()
        ttft: float | None = None
        response_text = ""
        input_tokens = 0
        output_tokens = 0
        finish_reason = "unknown"
        finish_confidence = "unknown"

        messages = []
        if prompt.system_prompt:
            messages.append({"role": "system", "content": prompt.system_prompt})
        messages.append({"role": "user", "content": prompt.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": prompt.max_tokens,
            "temperature": prompt.temperature,
            "stream": True,
        }
        if prompt.stop_sequences:
            payload["stop"] = prompt.stop_sequences

        try:
            timeout = httpx.Timeout(float(prompt.app_timeout_seconds))
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await self._open_stream(client, payload)
                async with response:
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line.removeprefix("data: ").strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        choices = chunk.get("choices") or []
                        if choices:
                            choice = choices[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if content and ttft is None:
                                ttft = time.monotonic() - start
                            response_text += content
                            if choice.get("finish_reason"):
                                finish_reason = choice["finish_reason"]
                                finish_confidence = "confirmed"
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)

            total = time.monotonic() - start
            if output_tokens == 0:
                output_tokens = int(len(response_text.split()) * 1.3)
            if input_tokens == 0:
                input_tokens = int(len(prompt.prompt.split()) * 1.3)
            if finish_reason == "unknown":
                finish_reason = "length" if output_tokens >= prompt.max_tokens * 0.95 else "stop"
                finish_confidence = "inferred"
            gen_time = max(0.001, total - (ttft or 0))
            return BenchResult(
                prompt_id=prompt.id,
                prompt_name=prompt.name,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                prompt_eval_tps=round(input_tokens / max(ttft or 1, 0.001), 2),
                generation_tps=round(output_tokens / gen_time, 2),
                ttft_seconds=round(ttft or 0, 3),
                total_seconds=round(total, 2),
                finish_reason=finish_reason,
                finish_confidence=finish_confidence,
                response_preview=response_text[:500],
                response_full=response_text,
            )
        except Exception as exc:
            return BenchResult(
                prompt_id=prompt.id,
                prompt_name=prompt.name,
                model=model,
                total_seconds=round(time.monotonic() - start, 2),
                finish_reason="error",
                finish_confidence="confirmed",
                error=str(exc),
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
            results=results,
            avg_gen_tps=round(avg_tps, 2),
            avg_ttft=round(avg_ttft, 3),
            total_tokens=sum(result.output_tokens for result in results),
            total_seconds=round(sum(result.total_seconds for result in results), 2),
            truncated_count=sum(1 for result in results if result.finish_reason == "length"),
            error_count=sum(1 for result in results if result.error),
        )

    async def _open_stream(self, client: httpx.AsyncClient, payload: dict) -> httpx.Response:
        for path in ["/api/v1/chat/completions", "/v1/chat/completions"]:
            request = client.build_request("POST", f"{self.base_url}{path}", json=payload)
            response = await client.send(request, stream=True)
            if response.status_code < 400:
                return response
            await response.aclose()
        raise RuntimeError("No OpenAI-compatible chat completions endpoint accepted the benchmark request.")
