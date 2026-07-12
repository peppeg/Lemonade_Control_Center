"""Predefined benchmark suites."""
from __future__ import annotations

from app.services.bench.models import BenchPrompt, BenchSuite


def _prompt(
    prompt_id: str,
    name: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    expected_format: str,
    tags: list[str],
) -> BenchPrompt:
    return BenchPrompt(
        id=prompt_id,
        name=name,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        expected_format=expected_format,
        tags=tags,
    )


SUITES: dict[str, BenchSuite] = {
    "coding_agent": BenchSuite(
        id="coding_agent",
        name="Coding Agent Workflows",
        description="Repository-scale planning, patching, review, and failure diagnosis tasks for coding agents.",
        icon="agent",
        recommended_ctx=32768,
        recommended_temp=0.2,
        estimated_minutes=18,
        prompts=[
            _prompt("agent_patch", "Scoped Patch", "Given a Python service with a failing idempotency test, propose a minimal patch, list changed files, and include focused tests. Do not rewrite unrelated code.", 3000, 0.2, "text", ["agent", "patch"]),
            _prompt("agent_review", "Review Findings", "Review a hypothetical pull request that adds retry logic around an HTTP stream. Report only actionable correctness, resource-lifetime, and test-coverage findings ordered by severity.", 2600, 0.2, "text", ["agent", "review"]),
            _prompt("agent_debug", "CI Diagnosis", "A Linux CI job passes locally but fails with read-only filesystem errors and leaked async responses. Produce an evidence-driven diagnosis and a safe validation plan.", 2600, 0.2, "text", ["agent", "debug"]),
        ],
    ),
    "coding": BenchSuite(
        id="coding",
        name="Coding",
        description="Code generation, refactoring, and API implementation tasks.",
        icon="code",
        recommended_temp=0.3,
        estimated_minutes=15,
        prompts=[
            _prompt("code_bst", "Binary Search Tree", "Write a Python binary search tree with insert, delete, search, type hints, and docstrings.", 3000, 0.3, "code", ["python"]),
            _prompt("code_api", "HTTP Client", "Write an async Python HTTP client with retries, backoff, rate limiting, and structured errors.", 3000, 0.3, "code", ["python", "api"]),
            _prompt("code_parser", "Log Parser", "Write a parser for journalctl output that extracts timestamp, level, service, and message as JSON.", 2500, 0.3, "code", ["parser"]),
        ],
    ),
    "executor": BenchSuite(
        id="executor",
        name="Executor Strict",
        description="Deterministic structured-output tasks for automation.",
        icon="executor",
        recommended_temp=0.0,
        estimated_minutes=8,
        prompts=[
            _prompt("exec_json", "JSON Schema", "Generate a JSON schema for a library catalog API. Output only valid JSON.", 2000, 0.0, "json", ["json"]),
            _prompt("exec_sql", "SQL Query", "Write one PostgreSQL query for top customers by total order value in the last 90 days. Output only SQL.", 1200, 0.0, "code", ["sql"]),
            _prompt("exec_cli", "CLI Help", "Generate --help output for a CLI named lcc with status, models, config, logs, and bench commands.", 1800, 0.0, "text", ["cli"]),
        ],
    ),
    "long_context": BenchSuite(
        id="long_context",
        name="Long Context",
        description="Long-form analysis and extraction tasks.",
        icon="context",
        recommended_ctx=32768,
        estimated_minutes=20,
        prompts=[
            _prompt("long_summary", "Technical Summary", "Write a detailed overview of modern LLM inference servers: KV cache, batching, quantization, backends, and mmap.", 6000, 0.7, "text", ["long"]),
            _prompt("long_arch", "Architecture Plan", "Design a multi-tenant LLM serving platform with routing, queues, monitoring, health checks, and rollback strategy.", 7000, 0.7, "text", ["architecture"]),
        ],
    ),
    "reasoning": BenchSuite(
        id="reasoning",
        name="Reasoning",
        description="Logic, planning, and technical tradeoff tasks.",
        icon="reasoning",
        estimated_minutes=15,
        prompts=[
            _prompt("reason_math", "Placement Strategy", "Solve an LLM cluster placement problem with RAM and cold-start constraints. Show your reasoning.", 3000, 0.7, "text", ["math"]),
            _prompt("reason_debate", "mmap Debate", "Present both sides of using mmap versus loading an entire model into RAM. Finish with a recommendation matrix.", 3500, 0.7, "text", ["tradeoff"]),
        ],
    ),
}
