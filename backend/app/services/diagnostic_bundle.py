"""Diagnostic bundle collection and sanitization."""
from __future__ import annotations

import getpass
import io
import json
import platform
import re
import socket
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.capabilities import capabilities
from app.config import settings
from app.services.hardware import get_hardware_info, get_temperatures
from app.services.log_parser import get_recent_logs, parse_last_task
from app.services.process import find_llama_server, get_service_status
from app.services.run_evidence import RunEvidenceStorage
from app.services.setup import SetupService


SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|admin[_-]?key|authorization|bearer|token|secret|password|passwd|credential)",
    re.IGNORECASE,
)
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
HF_TOKEN_RE = re.compile(r"\bhf_[A-Za-z0-9_]{12,}\b")
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|admin[_-]?key|authorization|token|secret|password|passwd|credential)"
    r"(\s*[:=]\s*)([\"']?)([^\"'\s,}]+)"
)


class DiagnosticBundleSanitizer:
    """Redacts common secrets and personal host details from bundle entries."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.username = getpass.getuser()
        self.home = str(Path.home())
        self.hostname = socket.gethostname()

    def redact_data(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted: dict[Any, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if SENSITIVE_KEY_RE.search(key_text):
                    self._mark("secret_key")
                    redacted[key] = "[redacted]"
                else:
                    redacted[key] = self.redact_data(item)
            return redacted
        if isinstance(value, list):
            return [self.redact_data(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact_data(item) for item in value)
        if isinstance(value, str):
            return self.redact_text(value)
        return value

    def redact_text(self, text: str) -> str:
        redacted = text
        redacted = self._sub("bearer_token", BEARER_RE, "[redacted:bearer]", redacted)
        redacted = self._sub("hf_token", HF_TOKEN_RE, "[redacted:hf-token]", redacted)
        redacted = self._sub(
            "secret_assignment",
            SENSITIVE_ASSIGNMENT_RE,
            lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}[redacted]",
            redacted,
        )
        if self.home and self.home != "/":
            redacted = self._replace("home_path", self.home, "~", redacted)
        if self.username and len(self.username) >= 3:
            redacted = self._sub(
                "user_path",
                re.compile(rf"(?<=/home/){re.escape(self.username)}\b"),
                "<user>",
                redacted,
            )
        if self.hostname and len(self.hostname) >= 3:
            redacted = self._replace("hostname", self.hostname, "<host>", redacted)
        redacted = self._sub("private_ip", PRIVATE_IP_RE, "<private-ip>", redacted)
        return redacted

    def _replace(self, label: str, old: str, new: str, text: str) -> str:
        count = text.count(old)
        if count:
            self._mark(label, count)
            return text.replace(old, new)
        return text

    def _sub(self, label: str, pattern: re.Pattern, replacement, text: str) -> str:
        redacted, count = pattern.subn(replacement, text)
        if count:
            self._mark(label, count)
        return redacted

    def _mark(self, label: str, count: int = 1) -> None:
        self.counts[label] = self.counts.get(label, 0) + count


class DiagnosticBundleBuilder:
    """Collects diagnostics and writes a sanitized support archive."""

    def __init__(self, sanitizer: DiagnosticBundleSanitizer | None = None) -> None:
        self.sanitizer = sanitizer or DiagnosticBundleSanitizer()
        self.entries: dict[str, str] = {}
        self.errors: dict[str, str] = {}

    async def build(self) -> tuple[bytes, str]:
        self._collect_sync("target.json", _target_snapshot)
        self._collect_sync("hardware.json", get_hardware_info)
        self._collect_sync("temperatures.json", lambda: get_temperatures(timeout=2))
        self._collect_sync("llama_server.json", find_llama_server)
        self._collect_sync("service_status.json", lambda: get_service_status(timeout=2))
        self._collect_sync("last_task.json", lambda: parse_last_task(n_lines=120, timeout=3))
        self._collect_sync("run_evidence_summary.json", _run_evidence_summary)

        try:
            logs = get_recent_logs(n_lines=250, timeout=3)
            self.add_text("last_logs.txt", "\n".join(entry.raw for entry in logs.entries))
        except Exception as exc:
            self.errors["last_logs.txt"] = str(exc)

        self.add_json("capabilities.json", capabilities.model_dump())
        self.add_text("README.txt", _bundle_readme())
        self.add_json("manifest.json", self._manifest())

        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
        filename = f"lcc-diagnostic-{timestamp}.zip"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in sorted(self.entries.items()):
                archive.writestr(name, content)
        return buffer.getvalue(), filename

    def add_json(self, name: str, value: Any) -> None:
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        value = self.sanitizer.redact_data(value)
        self.entries[name] = json.dumps(value, indent=2, default=str)

    def add_text(self, name: str, value: str) -> None:
        self.entries[name] = self.sanitizer.redact_text(value)

    def _collect_sync(self, name: str, func: Callable[[], Any]) -> None:
        try:
            self.add_json(name, func())
        except Exception as exc:
            self.errors[name] = str(exc)

    def _manifest(self) -> dict[str, Any]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "lemonade_url": settings.lemonade_url,
            "lemonade_version": capabilities.lemonade_version,
            "probe_timestamp": capabilities.probe_timestamp,
            "os": platform.platform(),
            "python": platform.python_version(),
            "entries": sorted(name for name in self.entries if name != "manifest.json"),
            "errors": self.errors,
            "sanitization": {
                "enabled": True,
                "redactions": dict(sorted(self.sanitizer.counts.items())),
                "notes": [
                    "Secrets, bearer tokens, Hugging Face tokens, private LAN IPs, hostnames, and local home paths are redacted on a best-effort basis.",
                    "Review the archive before sharing it publicly; prompts, logs, model names, and paths may still contain sensitive context.",
                ],
            },
        }


def _target_snapshot() -> dict[str, Any]:
    setup = SetupService().get_public_config()
    return {
        "settings": {
            "lemonade_url": settings.lemonade_url,
            "lemonade_recipe_options_file": settings.lemonade_recipe_options_file,
            "app_host": settings.app_host,
            "app_port": settings.app_port,
            "lan_mode": settings.lan_mode,
            "require_auth": settings.require_auth,
            "enable_delete": settings.enable_delete,
            "enable_restart": settings.enable_restart,
            "enable_bench_lab": settings.enable_bench_lab,
        },
        "setup": setup.model_dump(),
    }


def _run_evidence_summary() -> dict[str, Any]:
    results = RunEvidenceStorage().get_all()
    return {
        "count": len(results),
        "results": [
            {
                "id": item.id,
                "kind": item.kind,
                "model_name": item.model_name,
                "success": item.success,
                "error": item.error,
                "load_message": item.load_message,
                "requested_backend": item.requested_backend,
                "requested_ctx_size": item.requested_ctx_size,
                "merge_args": item.merge_args,
                "save_options": item.save_options,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "generation_tps": item.generation_tps,
                "ttft_seconds": item.ttft_seconds,
                "total_seconds": item.total_seconds,
                "finish_reason": item.finish_reason,
                "finish_confidence": item.finish_confidence,
                "observed_pid": item.observed_pid,
                "observed_backend": item.observed_backend,
                "observed_ctx_size": item.observed_ctx_size,
                "process_rss_gb": item.process_rss_gb,
                "ram_used_before_gb": item.ram_used_before_gb,
                "ram_used_after_gb": item.ram_used_after_gb,
                "swap_used_before_gb": item.swap_used_before_gb,
                "swap_used_after_gb": item.swap_used_after_gb,
                "warnings": item.warnings,
                "timestamp": item.timestamp,
            }
            for item in results[:10]
        ],
        "omitted_fields": ["prompt", "response_text", "requested_llamacpp_args"],
    }


def _bundle_readme() -> str:
    return """Lemonade Control Center diagnostic bundle

This archive is generated for troubleshooting LCC and Lemonade runtime issues.

Sanitization is best effort. LCC redacts common secrets, bearer tokens, Hugging Face tokens, private LAN IPs, hostnames, local usernames, and home paths before writing files into this archive.

Before posting the bundle publicly, review its contents. Logs, model names, prompts, responses, local paths, or command lines can still reveal private workflow details.
"""
