import json

import httpx
import pytest

from app.models.completions import CompletionRequest
from app.services.completion_runner import CompletionRunner


def _request(**overrides) -> CompletionRequest:
    values = {
        "model": "test-model",
        "prompt": "Reply with LCC_SMOKE_OK",
        "max_tokens": 64,
        "temperature": 0.25,
        "timeout_seconds": 120,
        "stop_sequences": ["DONE"],
    }
    values.update(overrides)
    return CompletionRequest(**values)


def _sse_response(*events: str) -> httpx.Response:
    body = "\n\n".join(f"data: {event}" for event in events)
    return httpx.Response(200, text=f"{body}\n\n", headers={"content-type": "text/event-stream"})


@pytest.mark.asyncio
async def test_runner_handles_fallback_stream_and_closes_responses():
    requests: list[httpx.Request] = []
    responses: list[httpx.Response] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/chat/completions":
            response = httpx.Response(404, text="not found")
        else:
            response = _sse_response(
                '{"choices":[{"delta":{"content":"LCC_"}}]}',
                '{"choices":[{"delta":{"content":"SMOKE_OK"},"finish_reason":"stop"}],"usage":{"prompt_tokens":6,"completion_tokens":3}}',
                "[DONE]",
            )
        responses.append(response)
        return response

    runner = CompletionRunner("http://lemonade.test", transport=httpx.MockTransport(handler))
    result = await runner.run(_request())

    assert result.success is True
    assert result.response_text == "LCC_SMOKE_OK"
    assert result.input_tokens == 6
    assert result.output_tokens == 3
    assert result.token_count_source == "api"
    assert result.finish_reason == "stop"
    assert result.finish_confidence == "confirmed"
    assert result.endpoint == "/v1/chat/completions"
    assert [request.url.path for request in requests] == [
        "/api/v1/chat/completions",
        "/v1/chat/completions",
    ]
    assert all(response.is_closed for response in responses)
    payload = json.loads(requests[-1].content)
    assert payload["max_tokens"] == 64
    assert payload["temperature"] == 0.25
    assert payload["stop"] == ["DONE"]


@pytest.mark.asyncio
async def test_runner_ignores_null_content_and_separates_reasoning():
    def handler(request: httpx.Request) -> httpx.Response:
        return _sse_response(
            '{"choices":[{"delta":{"role":"assistant","content":null}}]}',
            '{"choices":[{"delta":{"reasoning_content":"Think first. "}}]}',
            '{"choices":[{"delta":{"content":[{"type":"text","text":"LCC_"},{"type":"text","text":{"value":"SMOKE_OK"}}]}}]}',
            '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
            "[DONE]",
        )

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is True
    assert result.response_text == "LCC_SMOKE_OK"
    assert result.reasoning_text == "Think first. "
    assert result.token_count_source == "estimated"
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_runner_marks_partial_api_usage_as_mixed():
    def handler(request: httpx.Request) -> httpx.Response:
        return _sse_response(
            '{"choices":[{"delta":{"content":"two words"},"finish_reason":"stop"}],"usage":{"prompt_tokens":7}}',
            "[DONE]",
        )

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.input_tokens == 7
    assert result.output_tokens > 0
    assert result.token_count_source == "mixed"


@pytest.mark.asyncio
async def test_runner_skips_malformed_event_when_valid_output_follows():
    def handler(request: httpx.Request) -> httpx.Response:
        return _sse_response(
            "not-json",
            '{"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}',
            "[DONE]",
        )

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is True
    assert result.response_text == "ok"
    assert result.warnings == ["Skipped a malformed JSON event in the completion stream."]


@pytest.mark.asyncio
async def test_runner_preserves_output_and_warns_when_done_is_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return _sse_response('{"choices":[{"delta":{"content":"partial complete"},"finish_reason":"stop"}]}')

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is True
    assert result.response_text == "partial complete"
    assert result.warnings == ["Completion stream ended without a [DONE] event."]


@pytest.mark.asyncio
async def test_runner_returns_structured_stream_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _sse_response('{"error":{"message":"model unavailable"}}')

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is False
    assert result.error is not None
    assert result.error.kind == "protocol"
    assert result.error.message == "Completion stream reported an error: model unavailable"


@pytest.mark.asyncio
async def test_runner_returns_empty_response_error_for_metadata_only_stream():
    def handler(request: httpx.Request) -> httpx.Response:
        return _sse_response(
            '{"choices":[{"delta":{"role":"assistant","content":null}}]}',
            '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
            "[DONE]",
        )

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is False
    assert result.error is not None
    assert result.error.kind == "empty_response"
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_runner_returns_structured_http_error_and_closes_rejections():
    responses: list[httpx.Response] = []

    def handler(request: httpx.Request) -> httpx.Response:
        response = httpx.Response(404, text=f"missing {request.url.path}")
        responses.append(response)
        return response

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is False
    assert result.error is not None
    assert result.error.kind == "http"
    assert result.error.status_code == 404
    assert "/api/v1/chat/completions: HTTP 404" in result.error.message
    assert all(response.is_closed for response in responses)


class InterruptingStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self):
        yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        raise httpx.ReadError("stream interrupted")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_runner_preserves_partial_output_when_stream_is_interrupted():
    stream = InterruptingStream()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream, headers={"content-type": "text/event-stream"})

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is False
    assert result.response_text == "partial"
    assert result.error is not None
    assert result.error.kind == "connection"
    assert result.token_count_source == "estimated"
    assert stream.closed is True


@pytest.mark.asyncio
async def test_runner_returns_structured_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    result = await CompletionRunner(
        "http://lemonade.test",
        transport=httpx.MockTransport(handler),
    ).run(_request())

    assert result.success is False
    assert result.error is not None
    assert result.error.kind == "timeout"
    assert result.error.message == "Completion request timed out."
