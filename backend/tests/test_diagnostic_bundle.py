import json

import pytest

from app.models.schemas import RunEvidenceSeed
from app.services.diagnostic_bundle import DiagnosticBundleBuilder, DiagnosticBundleSanitizer, _run_evidence_summary


def test_sanitizer_redacts_structured_secrets_and_host_details():
    sanitizer = DiagnosticBundleSanitizer()
    sanitizer.username = "alice"
    sanitizer.home = "/home/alice"
    sanitizer.hostname = "corsaro"

    data = {
        "lemonade_admin_api_key": "super-secret",
        "url": "http://192.168.31.41:13305",
        "model_path": "/home/alice/models/qwen.gguf",
        "host": "corsaro",
        "nested": {"hf_token": "hf_abcdefghijklmnopqrstuvwxyz"},
    }

    redacted = sanitizer.redact_data(data)
    serialized = json.dumps(redacted)

    assert "super-secret" not in serialized
    assert "192.168.31.41" not in serialized
    assert "/home/alice" not in serialized
    assert "corsaro" not in serialized
    assert "hf_abcdefghijklmnopqrstuvwxyz" not in serialized
    assert redacted["lemonade_admin_api_key"] == "[redacted]"
    assert redacted["url"] == "http://<private-ip>:13305"
    assert redacted["model_path"] == "~/models/qwen.gguf"
    assert redacted["host"] == "<host>"
    assert redacted["nested"]["hf_token"] == "[redacted]"


def test_sanitizer_keeps_non_secret_token_counts_and_configured_flags():
    sanitizer = DiagnosticBundleSanitizer()

    data = {
        "input_tokens": 123,
        "output_tokens": 456,
        "token_count_source": "estimated",
        "admin_key_configured": True,
        "redactions": {"secret_key": 2, "bearer_token": 1},
    }

    redacted = sanitizer.redact_data(data)

    assert redacted == data


def test_sanitizer_redacts_raw_log_tokens():
    sanitizer = DiagnosticBundleSanitizer()
    sanitizer.username = "alice"
    sanitizer.home = "/home/alice"
    sanitizer.hostname = "corsaro"

    text = (
        "Authorization: Bearer abc.def.ghi\n"
        "HF_TOKEN=hf_abcdefghijklmnopqrstuvwxyz\n"
        "config at /home/alice/.cache on corsaro 10.0.0.5\n"
    )

    redacted = sanitizer.redact_text(text)

    assert "abc.def.ghi" not in redacted
    assert "hf_abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "/home/alice" not in redacted
    assert "corsaro" not in redacted
    assert "10.0.0.5" not in redacted
    assert "Authorization: [redacted]" in redacted
    assert "HF_TOKEN=[redacted:hf-token]" in redacted
    assert "<private-ip>" in redacted


def test_bundle_builder_records_manifest_sanitization_counts():
    sanitizer = DiagnosticBundleSanitizer()
    sanitizer.username = "alice"
    sanitizer.home = "/home/alice"
    sanitizer.hostname = "corsaro"
    builder = DiagnosticBundleBuilder(sanitizer=sanitizer)

    builder.add_json("config.json", {"token": "secret", "path": "/home/alice/file"})
    builder.add_text("logs.txt", "server corsaro at 192.168.1.20")
    manifest = builder._manifest()

    assert "secret" not in builder.entries["config.json"]
    assert "/home/alice" not in builder.entries["config.json"]
    assert "corsaro" not in builder.entries["logs.txt"]
    assert "192.168.1.20" not in builder.entries["logs.txt"]
    assert manifest["sanitization"]["enabled"] is True
    assert manifest["sanitization"]["redactions"]["secret_key"] == 1
    assert manifest["sanitization"]["redactions"]["private_ip"] == 1


@pytest.mark.asyncio
async def test_bundle_builder_records_unavailable_backend_readiness(monkeypatch):
    class FailingProvider:
        async def get_system_info(self):
            raise RuntimeError("Lemonade offline")

    monkeypatch.setattr("app.dependencies.get_provider", lambda: FailingProvider())
    builder = DiagnosticBundleBuilder()

    await builder._collect_backend_readiness()

    readiness = json.loads(builder.entries["backend_readiness.json"])
    assert readiness["status"] == "unavailable"
    assert readiness["available"] is False
    assert readiness["items"] == []
    assert builder.errors["backend_readiness.json"] == "Lemonade offline"


def test_run_evidence_summary_keeps_safe_identity_and_omits_sensitive_content(monkeypatch):
    evidence = RunEvidenceSeed(
        id="run-1",
        model_name="qwen",
        requested_model_name="qwen:latest",
        observed_model_name="qwen",
        runtime_id="runtime-a",
        runtime_label="Local Lemonade",
        runtime_server_url="http://192.168.1.20:13305",
        workflow_profile_id="coding",
        workflow_profile_name="Coding Fast",
        prompt="private prompt",
        response_text="private response",
        request_stop_sequences=["private stop"],
        requested_llamacpp_args="--secret-like-value",
        error="Could not connect to http://private.example.test:13305",
        load_message="Server private.example.test rejected the load",
    )

    class Storage:
        def get_all(self):
            return [evidence]

    monkeypatch.setattr("app.services.diagnostic_bundle.RunEvidenceStorage", Storage)

    summary = _run_evidence_summary()
    serialized = json.dumps(summary, default=str)

    assert summary["results"][0]["runtime_id"] == "runtime-a"
    assert summary["results"][0]["workflow_profile_id"] == "coding"
    assert "runtime_server_url" in summary["omitted_fields"]
    assert "192.168.1.20" not in serialized
    assert "private prompt" not in serialized
    assert "private response" not in serialized
    assert "private stop" not in serialized
    assert "secret-like-value" not in serialized
    assert "private.example.test" not in serialized
