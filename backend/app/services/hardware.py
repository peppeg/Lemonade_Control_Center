"""
Hardware monitoring service using psutil and system commands.

Provides: RAM, CPU, disk, temperatures, top processes.
"""
import platform
import subprocess
from pathlib import Path

import psutil

from app.models.schemas import (
    HardwareInfo,
    TemperaturesResponse,
    TemperatureReading,
    TopProcessInfo,
    TopProcessesResponse,
)


def get_hardware_info(model_cache_path: str | None = None) -> HardwareInfo:
    """Get current hardware status snapshot."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    cpu_count = psutil.cpu_count() or 1
    gpu_info = get_gpu_info()

    disk_info = {}
    disk_path = model_cache_path
    for path_candidate in [
        model_cache_path,
        "/opt/var/lib/lemonade",
        str(psutil.Path.home() / ".cache" / "lemonade") if hasattr(psutil, 'Path') else None,
        "/",
    ]:
        if path_candidate:
            try:
                du = psutil.disk_usage(path_candidate)
                disk_info = {
                    "disk_total_gb": round(du.total / (1024**3), 1),
                    "disk_used_gb": round(du.used / (1024**3), 1),
                    "disk_free_gb": round(du.free / (1024**3), 1),
                    "disk_percent": du.percent,
                    "disk_path": path_candidate,
                }
                break
            except (FileNotFoundError, PermissionError):
                continue

    return HardwareInfo(
        ram_total_gb=round(mem.total / (1024**3), 1),
        ram_used_gb=round(mem.used / (1024**3), 1),
        ram_available_gb=round(mem.available / (1024**3), 1),
        ram_percent=mem.percent,
        swap_total_gb=round(swap.total / (1024**3), 1),
        swap_used_gb=round(swap.used / (1024**3), 1),
        cpu_percent=cpu,
        cpu_count=cpu_count,
        **gpu_info,
        **disk_info,
    )


def get_gpu_info() -> dict:
    """Read lightweight AMDGPU telemetry from sysfs when available."""
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
        device = card / "device"
        vendor = _read_text(device / "vendor")
        if vendor and vendor.lower() != "0x1002":
            continue

        load = _read_float(device / "gpu_busy_percent")
        temp = _read_amdgpu_temp_c(device)
        if load is None and temp is None:
            continue

        return {
            "gpu_available": True,
            "gpu_name": card.name,
            "gpu_load_percent": load,
            "gpu_temp_c": temp,
        }

    return {
        "gpu_available": False,
        "gpu_name": None,
        "gpu_load_percent": None,
        "gpu_temp_c": None,
    }


def _read_amdgpu_temp_c(device: Path) -> float | None:
    for temp_path in sorted(device.glob("hwmon/hwmon*/temp1_input")):
        value = _read_float(temp_path)
        if value is not None:
            return round(value / 1000, 1)
    return None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _read_float(path: Path) -> float | None:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_temperatures() -> TemperaturesResponse:
    """Get temperature readings from sensors."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            readings = []
            for chip_name, entries in temps.items():
                for entry in entries:
                    label = f"{chip_name}/{entry.label}" if entry.label else chip_name
                    readings.append(TemperatureReading(
                        label=label,
                        current=entry.current,
                        high=entry.high,
                        critical=entry.critical,
                    ))
            return TemperaturesResponse(readings=readings)
    except (AttributeError, RuntimeError):
        pass

    try:
        result = subprocess.run(
            ["sensors"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            readings = _parse_sensors_output(result.stdout)
            return TemperaturesResponse(readings=readings)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return TemperaturesResponse(
        readings=[], available=False,
        error="Temperature monitoring not available (psutil/sensors)"
    )


def _parse_sensors_output(output: str) -> list[TemperatureReading]:
    """Basic parser for `sensors` CLI output."""
    readings = []
    current_chip = ""
    for line in output.split("\n"):
        line = line.strip()
        if not line or line.startswith("Adapter:"):
            continue
        if ":" not in line and line:
            current_chip = line
            continue
        if "°C" in line and ":" in line:
            parts = line.split(":")
            label = f"{current_chip}/{parts[0].strip()}"
            temp_str = parts[1].strip()
            try:
                temp_val = float(
                    temp_str.split("°C")[0].replace("+", "").strip()
                )
                readings.append(TemperatureReading(
                    label=label, current=temp_val
                ))
            except (ValueError, IndexError):
                pass
    return readings


def get_top_processes(n: int = 10) -> TopProcessesResponse:
    """Get top N processes sorted by memory usage."""
    procs = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
        try:
            info = proc.info
            rss = (info.get("memory_info") or proc.memory_info()).rss
            procs.append(TopProcessInfo(
                pid=info["pid"],
                name=info["name"] or "unknown",
                rss_gb=round(rss / (1024**3), 2),
                cpu_percent=info.get("cpu_percent", 0) or 0,
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda p: p.rss_gb, reverse=True)
    return TopProcessesResponse(processes=procs[:n])
