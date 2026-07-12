"""Telemetry providers with explicit provenance and measurement quality."""
from __future__ import annotations

import json
import shutil
import subprocess

import psutil

from app.models.telemetry import TelemetryMetric, TelemetryQuality, TelemetrySample, TelemetrySnapshot
from app.services.hardware import get_gpu_info
from app.services.process import find_llama_server

class LinuxTelemetryProvider:
    id = "linux_process_sysfs"
    label = "Linux process/sysfs"

    def sample(self, phase: str = "point") -> TelemetrySample:
        metrics: list[TelemetryMetric] = []
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            metrics.extend(
                [
                    self._metric("host.ram_used", round(memory.used / 1024**3, 2), "GB", "measured", "/proc via psutil"),
                    self._metric("host.swap_used", round(swap.used / 1024**3, 2), "GB", "measured", "/proc via psutil"),
                    self._metric("host.cpu_busy", psutil.cpu_percent(interval=None), "%", "measured", "/proc via psutil"),
                ]
            )
        except Exception as exc:
            return TelemetrySample(
                provider_id=self.id,
                provider_label=self.label,
                phase=phase,
                quality="degraded",
                error=f"Host telemetry failed: {exc}",
            )

        try:
            process = find_llama_server()
            if process.found and process.process:
                metrics.extend(
                    [
                        self._metric("llama.pid", process.process.pid, None, "measured", "matching local process"),
                        self._metric("llama.rss", process.process.rss_gb, "GB", "measured", "/proc process RSS"),
                        self._metric("llama.cpu_busy", process.process.cpu_percent, "%", "measured", "/proc process CPU"),
                    ]
                )
            else:
                metrics.append(self._metric("llama.rss", None, "GB", "unavailable", "llama-server process not found"))
        except Exception as exc:
            metrics.append(self._metric("llama.rss", None, "GB", "degraded", f"process probe failed: {exc}"))

        gpu = get_gpu_info()
        if gpu.get("gpu_available"):
            device = str(gpu.get("gpu_name") or "AMDGPU")
            if gpu.get("gpu_load_percent") is not None:
                metrics.append(self._metric("gpu.busy", gpu["gpu_load_percent"], "%", "measured", "AMDGPU sysfs gpu_busy_percent", device))
            if gpu.get("gpu_temp_c") is not None:
                metrics.append(self._metric("gpu.temperature", gpu["gpu_temp_c"], "C", "measured", "AMDGPU hwmon sysfs", device))
        else:
            metrics.append(self._metric("gpu.busy", None, "%", "unsupported", "No readable AMDGPU sysfs counters"))

        quality: TelemetryQuality = "measured" if any(metric.quality == "measured" for metric in metrics) else "unavailable"
        return TelemetrySample(
            provider_id=self.id,
            provider_label=self.label,
            phase=phase,
            quality=quality,
            available=quality == "measured",
            metrics=metrics,
        )

    def _metric(self, name, value, unit, quality, evidence, device=None) -> TelemetryMetric:
        return TelemetryMetric(
            name=name,
            value=value,
            unit=unit,
            quality=quality,
            provider_id=self.id,
            device=device,
            evidence=evidence,
        )


class JsonCommandTelemetryProvider:
    def __init__(self, provider_id: str, label: str, executable: str, args: list[str], kind: str) -> None:
        self.id = provider_id
        self.label = label
        self.executable = executable
        self.args = args
        self.kind = kind

    def sample(self, phase: str = "point") -> TelemetrySample:
        command = shutil.which(self.executable)
        if not command:
            return TelemetrySample(
                provider_id=self.id,
                provider_label=self.label,
                phase=phase,
                quality="unsupported",
                error=f"{self.executable} is not installed.",
            )
        try:
            result = subprocess.run([command, *self.args], capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return self._degraded(phase, f"command failed: {exc}")
        if result.returncode != 0:
            return self._degraded(phase, f"command exited {result.returncode}: {result.stderr.strip()[:200]}")
        try:
            payload = _last_json_value(result.stdout)
        except ValueError as exc:
            return self._degraded(phase, str(exc))
        metrics = _amdgpu_metrics(payload, self.id) if self.kind == "amdgpu" else _xdna_metrics(payload, self.id)
        if not metrics:
            return self._degraded(phase, "JSON output contained no recognized telemetry metrics.")
        return TelemetrySample(
            provider_id=self.id,
            provider_label=self.label,
            phase=phase,
            quality="measured",
            available=True,
            metrics=metrics,
        )

    def _degraded(self, phase: str, error: str) -> TelemetrySample:
        return TelemetrySample(
            provider_id=self.id,
            provider_label=self.label,
            phase=phase,
            quality="degraded",
            error=error,
        )


class TelemetryManager:
    def __init__(self, providers: list | None = None) -> None:
        self.providers = providers or [
            LinuxTelemetryProvider(),
            JsonCommandTelemetryProvider("amdgpu_top", "amdgpu_top", "amdgpu_top", ["--json", "-n", "1"], "amdgpu"),
            JsonCommandTelemetryProvider("xdna_top", "xdna-top", "xdna-top", ["--json"], "xdna"),
        ]

    def snapshot(self, phase: str = "point") -> TelemetrySnapshot:
        samples: list[TelemetrySample] = []
        for provider in self.providers:
            try:
                samples.append(provider.sample(phase))
            except Exception as exc:
                samples.append(
                    TelemetrySample(
                        provider_id=getattr(provider, "id", "unknown"),
                        provider_label=getattr(provider, "label", "Unknown provider"),
                        phase=phase,
                        quality="degraded",
                        error=f"Provider failed: {exc}",
                    )
                )
        return TelemetrySnapshot(samples=samples)


def _last_json_value(output: str):
    decoder = json.JSONDecoder()
    values = []
    index = 0
    while index < len(output):
        while index < len(output) and output[index].isspace():
            index += 1
        if index >= len(output):
            break
        try:
            value, end = decoder.raw_decode(output, index)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON telemetry output: {exc}") from exc
        values.append(value)
        index = end
    if not values:
        raise ValueError("Telemetry command returned no JSON.")
    return values[-1]


def _amdgpu_metrics(payload, provider_id: str) -> list[TelemetryMetric]:
    devices = payload.get("devices", []) if isinstance(payload, dict) else []
    metrics: list[TelemetryMetric] = []
    for device in devices if isinstance(devices, list) else []:
        if not isinstance(device, dict):
            continue
        info = device.get("Info", {})
        device_name = info.get("DeviceName") if isinstance(info, dict) else None
        activity = device.get("gpu_activity", {})
        if isinstance(activity, dict):
            for key, raw in activity.items():
                if isinstance(raw, dict) and isinstance(raw.get("value"), (int, float)):
                    metrics.append(TelemetryMetric(
                        name=f"gpu.activity.{str(key).lower()}",
                        value=raw["value"],
                        unit=raw.get("unit", "%"),
                        quality="measured",
                        provider_id=provider_id,
                        device=device_name,
                        evidence="amdgpu_top JSON gpu_activity",
                    ))
    return metrics


def _xdna_metrics(payload, provider_id: str) -> list[TelemetryMetric]:
    metrics: list[TelemetryMetric] = []
    for path, value in _numeric_leaves(payload):
        lowered = path.lower()
        if any(token in lowered for token in ("util", "busy", "power", "temperature", "temp")):
            unit = "%" if any(token in lowered for token in ("util", "busy")) else None
            metrics.append(TelemetryMetric(
                name=f"npu.{lowered}",
                value=value,
                unit=unit,
                quality="measured",
                provider_id=provider_id,
                evidence="xdna-top JSON field",
            ))
    return metrics


def _numeric_leaves(value, prefix: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _numeric_leaves(item, f"{prefix}.{key}".strip("."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _numeric_leaves(item, f"{prefix}.{index}".strip("."))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield prefix, value
