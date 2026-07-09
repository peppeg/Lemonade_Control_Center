import pytest
from fastapi import HTTPException

from app.providers.lemonade import (
    _canonical_model_name,
    _size_to_bytes,
    _validate_llamacpp_args,
)
from app.services.process import parse_cmdline


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (22.8, int(22.8 * 1024**3)),
        (1024, 1024),
        (None, None),
        (True, None),
    ],
)
def test_size_to_bytes(value, expected):
    assert _size_to_bytes(value) == expected


def test_canonical_model_name_removes_latest_suffix():
    assert _canonical_model_name("Qwen-Test-GGUF:latest") == "Qwen-Test-GGUF"


def test_safe_llamacpp_args_are_accepted():
    _validate_llamacpp_args("--flash-attn on --reasoning off")


@pytest.mark.parametrize(
    "value",
    [
        "--jinja",
        "-c 32768",
        "--model model.gguf",
        "--flm-args test",
        "flm_args=test",
        "--model-draft draft.gguf",
        "-md draft.gguf",
        "--spec-draft-model draft.gguf",
    ],
)
def test_lemonade_managed_llamacpp_args_are_rejected(value):
    with pytest.raises(HTTPException) as exc_info:
        _validate_llamacpp_args(value)

    assert exc_info.value.status_code == 400
    assert "managed by Lemonade" in exc_info.value.detail


def test_parse_cmdline_extracts_runtime_parameters():
    result = parse_cmdline(
        [
            "/opt/bin/llama-server-rocm",
            "-m",
            "/models/qwen.gguf",
            "-c",
            "262144",
            "-ngl",
            "999",
            "--no-mmap",
            "--reasoning-format",
            "none",
        ]
    )

    assert result.backend == "rocm"
    assert result.model_path == "/models/qwen.gguf"
    assert result.ctx_size == 262144
    assert result.ngl == 999
    assert result.mmap is False
    assert result.reasoning_format == "none"
