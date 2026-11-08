from pathlib import Path

from app.services.hardware import get_gpu_info


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_gpu_info_reports_vram_and_gtt_memory(tmp_path):
    device = tmp_path / "card0" / "device"
    _write(device / "vendor", "0x1002\n")
    _write(device / "gpu_busy_percent", "12\n")
    _write(device / "hwmon" / "hwmon3" / "temp1_input", "41000\n")
    _write(device / "mem_info_vram_used", str(156110848))
    _write(device / "mem_info_vram_total", str(1073741824))
    _write(device / "mem_info_gtt_used", str(9214984192))
    _write(device / "mem_info_gtt_total", str(115964116992))

    info = get_gpu_info(tmp_path)

    assert info["gpu_available"] is True
    assert info["gpu_load_percent"] == 12
    assert info["gpu_temp_c"] == 41.0
    assert info["gpu_vram_used_gb"] == 0.15
    assert info["gpu_vram_total_gb"] == 1.0
    assert info["gpu_gtt_used_gb"] == 8.58
    assert info["gpu_gtt_total_gb"] == 108.0


def test_gpu_info_leaves_memory_empty_when_sysfs_counters_are_missing(tmp_path):
    device = tmp_path / "card0" / "device"
    _write(device / "vendor", "0x1002\n")
    _write(device / "gpu_busy_percent", "0\n")

    info = get_gpu_info(tmp_path)

    assert info["gpu_available"] is True
    assert info["gpu_vram_used_gb"] is None
    assert info["gpu_gtt_used_gb"] is None


def test_gpu_info_skips_non_amd_cards(tmp_path):
    device = tmp_path / "card0" / "device"
    _write(device / "vendor", "0x10de\n")
    _write(device / "gpu_busy_percent", "50\n")

    assert get_gpu_info(tmp_path)["gpu_available"] is False
