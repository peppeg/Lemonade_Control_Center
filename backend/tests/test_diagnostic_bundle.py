import json

from app.services.diagnostic_bundle import DiagnosticBundleBuilder, DiagnosticBundleSanitizer


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
