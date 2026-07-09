from app.models.schemas import LogEntryLevel
from app.services.log_parser import _parse_log_line


def test_backend_install_line_is_backend_event():
    entry = _parse_log_line(
        "2026-07-09 16:57:15.094 [Info] (Server) "
        "Installing backend: llamacpp:vulkan"
    )

    assert entry.level == LogEntryLevel.BACKEND


def test_llama_server_upgrade_line_is_update_event():
    entry = _parse_log_line(
        "2026-07-09 16:57:15.395 [Info] (llamacpp Server) "
        "Upgrading llama-server from b9585 to b9747"
    )

    assert entry.level == LogEntryLevel.UPDATE


def test_model_update_line_is_update_event():
    entry = _parse_log_line(
        "2026-07-09 06:21:31.980 [Info] (ModelManager) "
        "Update available for unsloth/Qwen3.6-27B-MTP-GGUF: "
        "cached=b3a58239d8d4, latest=5cb35eb3dcbf (1 variant(s))"
    )

    assert entry.level == LogEntryLevel.UPDATE


def test_expected_nvidia_detection_error_on_amd_is_warning():
    entry = _parse_log_line(
        "2026-07-09 06:21:31.185 [Info] (ModelManager) "
        "- NVIDIA GPU: detection error: No NVIDIA discrete GPU found"
    )

    assert entry.level == LogEntryLevel.WARNING


def test_warning_marker_with_error_text_is_warning():
    entry = _parse_log_line(
        "[2026/07/09 06:21:30:9138] W: [null wsi]: "
        "lws_socket_bind: setsockopt bind to device 127.0.0.1 error fd 3 (19)"
    )

    assert entry.level == LogEntryLevel.WARNING
