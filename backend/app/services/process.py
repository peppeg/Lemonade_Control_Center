"""
Process monitoring service — finds and parses the llama-server process.

Reads /proc/PID/cmdline to extract runtime parameters like ctx_size,
backend, ngl, mmap, MTP, reasoning format, etc.
"""
import re
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime

import psutil

from app.models.schemas import (
    LlamaServerInfoResponse,
    LlamaServerParams,
    ProcessInfo,
    ServiceStatusResponse,
)


def find_llama_server(pid: int | None = None, port: int | None = None) -> LlamaServerInfoResponse:
    """Find the llama-server process and parse its command line.

    With `pid` or `port`, as reported by Lemonade for a model, only a process that
    matches is returned. The port also works when Lemonade runs in its own PID
    namespace, where its pids mean nothing here.
    """
    servers = find_llama_servers()
    if pid is None and port is None:
        return servers[0] if servers else LlamaServerInfoResponse(found=False)
    return match_llama_server(servers, pid=pid, port=port)


def match_llama_server(
    servers: Sequence[LlamaServerInfoResponse], pid: int | None = None, port: int | None = None
) -> LlamaServerInfoResponse:
    """The one of `servers` with this port or pid."""

    def matches(server: LlamaServerInfoResponse) -> tuple[bool, bool]:
        return (
            port is not None and server.params is not None and server.params.port == port,
            pid is not None and server.process is not None and server.process.pid == pid,
        )

    best = max(servers, key=matches, default=None)
    return best if best is not None and any(matches(best)) else LlamaServerInfoResponse(found=False)


def find_llama_servers() -> list[LlamaServerInfoResponse]:
    """Find every llama-server process on this host, by executable."""
    servers: list[LlamaServerInfoResponse] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "status",
                                      "memory_info", "cpu_percent",
                                      "create_time"]):
        try:
            name = proc.info["name"] or ""
            cmdline = proc.info.get("cmdline") or []
            if proc.info.get("status") == psutil.STATUS_ZOMBIE or not _is_llama_server(name, cmdline):
                continue

            mem = proc.info.get("memory_info") or proc.memory_info()
            create_time = proc.info.get("create_time")
            now = datetime.now(UTC).timestamp()
            servers.append(
                LlamaServerInfoResponse(
                    found=True,
                    process=ProcessInfo(
                        pid=proc.info["pid"],
                        name=name,
                        cpu_percent=proc.info.get("cpu_percent", 0) or 0,
                        rss_gb=round(mem.rss / (1024**3), 2),
                        vms_gb=round(mem.vms / (1024**3), 2),
                        status=proc.info.get("status", "unknown"),
                        create_time=datetime.fromtimestamp(create_time, tz=UTC) if create_time else None,
                        uptime_seconds=round(now - create_time, 0) if create_time else None,
                    ),
                    params=parse_cmdline(cmdline),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return servers


def _is_llama_server(name: str, cmdline: list[str]) -> bool:
    """True for a process whose own executable is llama-server.

    Arguments are not considered: a shell, an editor, or a `grep` that mentions
    llama-server is another program, and its command line may hold secrets.
    """
    candidates = [name, cmdline[0] if cmdline else ""]
    return any(
        re.split(r"[\\/]", candidate)[-1].lower().startswith(("llama-server", "llama_server"))
        for candidate in candidates
    )


def parse_cmdline(cmdline: list[str]) -> LlamaServerParams:
    """Parse llama-server command line arguments into structured params."""
    raw = " ".join(cmdline)
    params = LlamaServerParams(raw_cmdline=raw)

    if cmdline:
        params.executable = cmdline[0]

    i = 0
    while i < len(cmdline):
        arg = cmdline[i]
        next_val = cmdline[i + 1] if i + 1 < len(cmdline) else None

        match arg:
            case "-m" | "--model":
                params.model_path = next_val
                i += 2
            case "--ctx-size" | "-c":
                params.ctx_size = _int(next_val)
                i += 2
            case "--port" | "-p":
                params.port = _int(next_val)
                i += 2
            case "--host":
                params.host = next_val
                i += 2
            case "-ngl" | "--n-gpu-layers":
                params.ngl = _int(next_val)
                i += 2
            case "--no-mmap":
                params.mmap = False
                i += 1
            case "--mmap":
                params.mmap = True
                i += 1
            case "--jinja":
                params.jinja = True
                i += 1
            case "--mmproj":
                params.mmproj = next_val
                i += 2
            case "--context-shift":
                params.context_shift = True
                i += 1
            case "--no-context-shift":
                params.context_shift = False
                i += 1
            case "--keep":
                params.keep = _int(next_val)
                i += 2
            case "--reasoning-format":
                params.reasoning_format = next_val
                i += 2
            case "--spec-type":
                params.spec_type = next_val
                i += 2
            case "--spec-draft-n-max":
                params.spec_draft_n_max = _int(next_val)
                i += 2
            case "--spec-draft-p-min":
                params.spec_draft_p_min = _float(next_val)
                i += 2
            case _:
                i += 1

    if params.executable and "vulkan" in params.executable.lower():
        params.backend = "vulkan"
    elif params.executable and "rocm" in params.executable.lower():
        params.backend = "rocm"
    elif params.ngl == 0:
        params.backend = "cpu"

    return params


def get_service_status(service_name: str = "lemond.service", timeout: float = 5) -> ServiceStatusResponse:
    """Get systemd service status."""
    try:
        result = subprocess.run(
            ["systemctl", "status", service_name, "--no-pager"],
            capture_output=True, text=True, timeout=timeout,
        check=False,
        )

        output = result.stdout + result.stderr
        active = "active (running)" in output

        if "active (running)" in output:
            status = "active"
        elif "inactive" in output:
            status = "inactive"
        elif "failed" in output:
            status = "failed"
        elif "could not be found" in output.lower():
            status = "not-found"
        else:
            status = "unknown"

        return ServiceStatusResponse(
            active=active, status=status, raw_output=output
        )
    except FileNotFoundError:
        return ServiceStatusResponse(
            active=False, status="not-found",
            raw_output="systemctl not found", available=False
        )
    except subprocess.TimeoutExpired:
        return ServiceStatusResponse(
            active=False, status="unknown",
            raw_output="systemctl timed out", available=False
        )


def restart_service(service_name: str = "lemond.service") -> tuple[bool, str]:
    """Restart a systemd service. Returns (success, message)."""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True, text=True, timeout=30,
        check=False,
        )
        if result.returncode == 0:
            return True, f"Service {service_name} restarted successfully."
        else:
            return False, f"Restart failed: {result.stderr.strip()}"
    except FileNotFoundError:
        return False, "systemctl not found"
    except subprocess.TimeoutExpired:
        return False, "Restart timed out (30s)"


def _int(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _float(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None
