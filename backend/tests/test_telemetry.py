import json
from types import SimpleNamespace

from app.services.telemetry import (
    JsonCommandTelemetryProvider,
    LinuxTelemetryProvider,
    TelemetryManager,
    _last_json_value,
)
from app.models.telemetry import TelemetrySample


def test_linux_provider_labels_measured_and_unsupported_metrics(monkeypatch):
    monkeypatch.setattr("app.services.telemetry.psutil.virtual_memory", lambda: SimpleNamespace(used=20 * 1024**3))
    monkeypatch.setattr("app.services.telemetry.psutil.swap_memory", lambda: SimpleNamespace(used=2 * 1024**3))
    monkeypatch.setattr("app.services.telemetry.psutil.cpu_percent", lambda interval=None: 12.5)
    monkeypatch.setattr(
        "app.services.telemetry.find_llama_server",
        lambda: SimpleNamespace(
            found=True,
            process=SimpleNamespace(pid=42, rss_gb=3.5, cpu_percent=8.0),
        ),
    )
    monkeypatch.setattr(
        "app.services.telemetry.get_gpu_info",
        lambda: {"gpu_available": True, "gpu_name": "card0", "gpu_load_percent": 73, "gpu_temp_c": 61.5},
    )

    sample = LinuxTelemetryProvider().sample("start")

    assert sample.quality == "measured"
    assert sample.phase == "start"
    assert {metric.name for metric in sample.metrics} >= {"host.ram_used", "llama.rss", "gpu.busy"}
    assert all(metric.quality == "measured" for metric in sample.metrics)
    assert next(metric for metric in sample.metrics if metric.name == "gpu.busy").evidence == "AMDGPU sysfs gpu_busy_percent"


def test_optional_command_provider_reports_unsupported_when_missing(monkeypatch):
    monkeypatch.setattr("app.services.telemetry.shutil.which", lambda executable: None)
    provider = JsonCommandTelemetryProvider("amdgpu_top", "amdgpu_top", "amdgpu_top", ["--json", "-n", "1"], "amdgpu")

    sample = provider.sample()

    assert sample.quality == "unsupported"
    assert sample.available is False
    assert "not installed" in sample.error


def test_amdgpu_top_provider_parses_last_streamed_json_sample(monkeypatch):
    payloads = [
        {"devices": [{"Info": {"DeviceName": "GPU 0"}, "gpu_activity": {"GFX": {"value": 10, "unit": "%"}}}]},
        {"devices": [{"Info": {"DeviceName": "GPU 0"}, "gpu_activity": {"GFX": {"value": 75, "unit": "%"}, "Memory": {"value": 20, "unit": "%"}}}]},
    ]
    monkeypatch.setattr("app.services.telemetry.shutil.which", lambda executable: "/usr/bin/amdgpu_top")
    monkeypatch.setattr(
        "app.services.telemetry.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="\n".join(json.dumps(item) for item in payloads), stderr=""),
    )
    provider = JsonCommandTelemetryProvider("amdgpu_top", "amdgpu_top", "amdgpu_top", ["--json", "-n", "1"], "amdgpu")

    sample = provider.sample("end")

    assert sample.quality == "measured"
    assert sample.phase == "end"
    assert [(metric.name, metric.value) for metric in sample.metrics] == [
        ("gpu.activity.gfx", 75),
        ("gpu.activity.memory", 20),
    ]


def test_xdna_provider_degrades_on_unrecognized_json(monkeypatch):
    monkeypatch.setattr("app.services.telemetry.shutil.which", lambda executable: "/usr/bin/xdna-top")
    monkeypatch.setattr(
        "app.services.telemetry.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='{"device":"npu0"}', stderr=""),
    )
    provider = JsonCommandTelemetryProvider("xdna_top", "xdna-top", "xdna-top", ["--json"], "xdna")

    sample = provider.sample()

    assert sample.quality == "degraded"
    assert "no recognized" in sample.error


def test_manager_never_claims_accelerator_ownership():
    provider = SimpleNamespace(
        id="fake",
        label="Fake",
        sample=lambda phase: TelemetrySample(provider_id="fake", provider_label="Fake", phase=phase, quality="unavailable"),
    )
    snapshot = TelemetryManager(providers=[provider]).snapshot()

    assert snapshot.accelerator_ownership == "unproven"
    assert "does not prove" in snapshot.ownership_note


def test_last_json_value_accepts_streamed_objects():
    assert _last_json_value('{"value":1}\n{"value":2}') == {"value": 2}
