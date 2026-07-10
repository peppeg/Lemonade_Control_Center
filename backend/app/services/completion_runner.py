"""Core OpenAI-compatible streaming runner shared by Smoke Test and Bench Lab."""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.models.completions import CompletionError, CompletionRequest, CompletionResult


COMPLETION_PATHS = ("/api/v1/chat/completions", "/v1/chat/completions")
MAX_ERROR_BODY_CHARS = 500


@dataclass
class _StreamState:
    response_text: str = ""
    reasoning_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    token_count_source: str = "unavailable"
    input_tokens_from_api: bool = False
    output_tokens_from_api: bool = False
    finish_reason: str = "unknown"
    finish_confidence: str = "unknown"
    ttft_seconds: float | None = None
    warnings: list[str] = field(default_factory=list)
    protocol_error: str | None = None
    done_received: bool = False


class CompletionRunner:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    async def run(self, request: CompletionRequest) -> CompletionResult:
        started = time.monotonic()
        payload = _payload(request)
        response: httpx.Response | None = None
        endpoint: str | None = None
        state = _StreamState()

        try:
            timeout = httpx.Timeout(float(request.timeout_seconds))
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self.transport,
                trust_env=False,
            ) as client:
                response, endpoint, http_error = await self._open_stream(client, payload)
                if response is None:
                    return self._error_result(request, started, http_error)

                try:
                    state = await _consume_stream(response, started, state)
                finally:
                    await response.aclose()
        except httpx.TimeoutException:
            return self._failure_result(
                request,
                started,
                state,
                CompletionError(kind="timeout", message="Completion request timed out.", endpoint=endpoint),
            )
        except httpx.TransportError:
            return self._failure_result(
                request,
                started,
                state,
                CompletionError(
                    kind="connection",
                    message=f"Completion runtime is not reachable at {self.base_url}.",
                    endpoint=endpoint,
                ),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return self._failure_result(
                request,
                started,
                state,
                CompletionError(kind="protocol", message=f"Invalid completion stream: {exc}", endpoint=endpoint),
            )
        except Exception as exc:
            return self._failure_result(
                request,
                started,
                state,
                CompletionError(
                    kind="protocol",
                    message=f"Completion stream could not be processed ({type(exc).__name__}).",
                    endpoint=endpoint,
                ),
            )

        total_seconds = time.monotonic() - started
        if state.protocol_error:
            return _result_from_state(
                request,
                state,
                total_seconds,
                endpoint,
                CompletionError(kind="protocol", message=state.protocol_error, endpoint=endpoint),
            )
        if not state.response_text:
            return _result_from_state(
                request,
                state,
                total_seconds,
                endpoint,
                CompletionError(
                    kind="empty_response",
                    message="Completion stream ended without assistant response text.",
                    endpoint=endpoint,
                ),
            )

        _finalize_metrics(state, request, total_seconds)
        return _result_from_state(request, state, total_seconds, endpoint)

    async def _open_stream(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> tuple[httpx.Response | None, str | None, CompletionError | None]:
        failures: list[str] = []
        last_status: int | None = None
        last_endpoint: str | None = None
        for path in COMPLETION_PATHS:
            last_endpoint = path
            request = client.build_request("POST", f"{self.base_url}{path}", json=payload)
            response = await client.send(request, stream=True)
            if response.status_code < 400:
                return response, path, None
            last_status = response.status_code
            try:
                body = (await response.aread()).decode(errors="replace")[:MAX_ERROR_BODY_CHARS].strip()
                failures.append(f"{path}: HTTP {response.status_code}{f' ({body})' if body else ''}")
            finally:
                await response.aclose()
        return None, last_endpoint, CompletionError(
            kind="http",
            message="No compatible completion endpoint accepted the request: " + "; ".join(failures),
            status_code=last_status,
            endpoint=last_endpoint,
        )

    def _error_result(
        self,
        request: CompletionRequest,
        started: float,
        error: CompletionError | None,
    ) -> CompletionResult:
        return CompletionResult(
            model=request.model,
            total_seconds=round(time.monotonic() - started, 2),
            error=error or CompletionError(kind="protocol", message="Unknown completion error."),
        )

    def _failure_result(
        self,
        request: CompletionRequest,
        started: float,
        state: _StreamState,
        error: CompletionError,
    ) -> CompletionResult:
        if state.response_text or state.reasoning_text:
            _finalize_token_counts(state, request)
        return _result_from_state(
            request,
            state,
            time.monotonic() - started,
            error.endpoint,
            error,
        )


async def _consume_stream(
    response: httpx.Response,
    started: float,
    state: _StreamState | None = None,
) -> _StreamState:
    state = state or _StreamState()
    async for event_data in _iter_sse_data(response):
        if event_data == "[DONE]":
            state.done_received = True
            break
        try:
            chunk = json.loads(event_data)
        except json.JSONDecodeError:
            state.warnings.append("Skipped a malformed JSON event in the completion stream.")
            continue
        if not isinstance(chunk, dict):
            state.warnings.append("Skipped a non-object event in the completion stream.")
            continue
        if chunk.get("error"):
            state.protocol_error = _protocol_error_message(chunk["error"])
            break

        _collect_usage(state, chunk.get("usage"))
        choices = chunk.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                delta = {}
            content = _extract_text(delta.get("content"))
            reasoning = _extract_text(delta.get("reasoning_content") or delta.get("reasoning"))
            if (content or reasoning) and state.ttft_seconds is None:
                state.ttft_seconds = time.monotonic() - started
            state.response_text += content
            state.reasoning_text += reasoning
            finish_reason = choice.get("finish_reason")
            if isinstance(finish_reason, str) and finish_reason:
                state.finish_reason = finish_reason
                state.finish_confidence = "confirmed"
    if not state.done_received:
        state.warnings.append("Completion stream ended without a [DONE] event.")
    return state


async def _iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line == "data":
            data_lines.append("")
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


def _payload(request: CompletionRequest) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "stream": True,
    }
    if request.stop_sequences:
        payload["stop"] = request.stop_sequences
    return payload


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_extract_text(item) for item in value)
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, dict):
            text = text.get("value")
        return text if isinstance(text, str) else ""
    return ""


def _collect_usage(state: _StreamState, usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    if isinstance(input_tokens, int) and input_tokens >= 0:
        state.input_tokens = input_tokens
        state.input_tokens_from_api = True
    if isinstance(output_tokens, int) and output_tokens >= 0:
        state.output_tokens = output_tokens
        state.output_tokens_from_api = True


def _finalize_metrics(state: _StreamState, request: CompletionRequest, total_seconds: float) -> None:
    _finalize_token_counts(state, request)
    if state.finish_reason == "unknown":
        state.finish_reason = "length" if state.output_tokens >= request.max_tokens * 0.95 else "stop"
        state.finish_confidence = "inferred"


def _finalize_token_counts(state: _StreamState, request: CompletionRequest) -> None:
    if not state.input_tokens_from_api:
        state.input_tokens = _estimate_tokens(request.prompt)
    if not state.output_tokens_from_api:
        state.output_tokens = _estimate_tokens(state.response_text)
    if state.input_tokens_from_api and state.output_tokens_from_api:
        state.token_count_source = "api"
    elif state.input_tokens_from_api or state.output_tokens_from_api:
        state.token_count_source = "mixed"
    else:
        state.token_count_source = "estimated"


def _result_from_state(
    request: CompletionRequest,
    state: _StreamState,
    total_seconds: float,
    endpoint: str | None,
    error: CompletionError | None = None,
) -> CompletionResult:
    ttft = state.ttft_seconds or 0.0
    generation_seconds = max(0.001, total_seconds - ttft)
    return CompletionResult(
        model=request.model,
        response_text=state.response_text,
        reasoning_text=state.reasoning_text,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
        token_count_source=state.token_count_source,
        prompt_eval_tps=round(state.input_tokens / max(ttft, 0.001), 2) if state.input_tokens else 0,
        generation_tps=round(state.output_tokens / generation_seconds, 2) if state.output_tokens else 0,
        ttft_seconds=round(ttft, 3),
        total_seconds=round(total_seconds, 2),
        finish_reason=state.finish_reason,
        finish_confidence=state.finish_confidence,
        endpoint=endpoint,
        warnings=state.warnings,
        error=error,
    )


def _estimate_tokens(text: str) -> int:
    return max(0, int(len(text.split()) * 1.3))


def _protocol_error_message(value: Any) -> str:
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str) and message:
            return f"Completion stream reported an error: {message[:MAX_ERROR_BODY_CHARS]}"
    if isinstance(value, str) and value:
        return f"Completion stream reported an error: {value[:MAX_ERROR_BODY_CHARS]}"
    return "Completion stream reported an unspecified error."
