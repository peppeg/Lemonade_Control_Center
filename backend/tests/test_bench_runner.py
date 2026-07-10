import pytest

from app.models.completions import CompletionError, CompletionResult
from app.services.bench.models import BenchPrompt
from app.services.bench.runner import BenchRunner


class FakeCompletionRunner:
    def __init__(self, result: CompletionResult) -> None:
        self.result = result
        self.last_request = None

    async def run(self, request):
        self.last_request = request
        return self.result


@pytest.mark.asyncio
async def test_bench_runner_adapts_prompt_and_completion_result():
    completion_runner = FakeCompletionRunner(
        CompletionResult(
            model="test-model",
            response_text="answer",
            reasoning_text="reasoning",
            input_tokens=4,
            output_tokens=2,
            token_count_source="api",
            prompt_eval_tps=20,
            generation_tps=10,
            ttft_seconds=0.2,
            total_seconds=0.4,
            finish_reason="stop",
            finish_confidence="confirmed",
            endpoint="/v1/chat/completions",
            warnings=["test warning"],
        )
    )
    runner = BenchRunner(completion_runner)
    prompt = BenchPrompt(
        id="quick",
        name="Quick",
        prompt="question",
        system_prompt="system",
        max_tokens=128,
        temperature=0.2,
        app_timeout_seconds=90,
        stop_sequences=["DONE"],
    )

    result = await runner.run_prompt(prompt, "test-model")

    assert completion_runner.last_request.model == "test-model"
    assert completion_runner.last_request.prompt == "question"
    assert completion_runner.last_request.system_prompt == "system"
    assert completion_runner.last_request.timeout_seconds == 90
    assert result.response_full == "answer"
    assert result.reasoning_text == "reasoning"
    assert result.token_count_source == "api"
    assert result.completion_endpoint == "/v1/chat/completions"
    assert result.warnings == ["test warning"]
    assert result.error is None


@pytest.mark.asyncio
async def test_bench_runner_preserves_structured_error_message():
    completion_runner = FakeCompletionRunner(
        CompletionResult(
            model="test-model",
            error=CompletionError(kind="timeout", message="Completion request timed out."),
        )
    )

    result = await BenchRunner(completion_runner).run_prompt(
        BenchPrompt(id="quick", name="Quick", prompt="question"),
        "test-model",
    )

    assert result.error == "Completion request timed out."
