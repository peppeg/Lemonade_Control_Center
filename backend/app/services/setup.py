"""First-run setup and persistent application settings."""
from __future__ import annotations

import json
import asyncio
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx

from app.capabilities import capabilities
from app.config import settings
from app.models.setup import (
    AppearanceConfig,
    CompleteSetupRequest,
    ConnectionDoctorCheck,
    ConnectionDoctorResponse,
    ConnectionTestResult,
    DiscoveryCheck,
    DiscoveryResult,
    LemonadeDiscoveryCandidate,
    LemonadeDiscoveryResponse,
    LccConfig,
    LccConfigPublic,
    RuntimeConfig,
    RuntimeConfigPublic,
    SetupConnectionRequest,
    SystemConfig,
)
from app.services.process import find_llama_server

CONFIG_FILE = Path(__file__).parent.parent / "data" / "config.json"
LEMONADE_BEACON_PORT = 13305
LEMONADE_FALLBACK_URLS = [
    "http://localhost:13305",
    "http://127.0.0.1:13305",
    "http://localhost:1234",
    "http://127.0.0.1:1234",
    "http://localhost:9000",
    "http://127.0.0.1:9000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]


class SetupService:
    """Manages setup wizard state and backend-owned configuration."""

    def __init__(self, config_file: Path = CONFIG_FILE):
        self.config_file = config_file
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def get_config(self) -> LccConfig:
        if not self.config_file.exists():
            return self._default_config()

        try:
            raw = json.loads(self.config_file.read_text(encoding="utf-8"))
            return LccConfig.model_validate(raw)
        except Exception:
            return self._default_config()

    def get_public_config(self) -> LccConfigPublic:
        return self._redact(self.get_config())

    def save_config(self, config: LccConfig) -> None:
        self.config_file.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    def is_setup_complete(self) -> bool:
        return self.get_config().setup_complete

    async def test_connection(self, req: SetupConnectionRequest) -> ConnectionTestResult:
        start = time.monotonic()
        url = req.url.rstrip("/")

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                if req.type == "lemonade":
                    headers = self._admin_headers(req.admin_key)
                    health = await client.get(f"{url}/api/v1/health", headers=headers)
                    health.raise_for_status()
                    data = health.json()
                    models_count = await self._count_lemonade_models(client, url, headers)
                    return ConnectionTestResult(
                        success=True,
                        version=str(data.get("version") or "unknown"),
                        models_count=models_count,
                        latency_ms=self._latency_ms(start),
                    )

                if req.type == "ollama":
                    version = await client.get(f"{url}/api/version")
                    version.raise_for_status()
                    data = version.json()
                    return ConnectionTestResult(
                        success=True,
                        version=str(data.get("version") or "unknown"),
                        latency_ms=self._latency_ms(start),
                    )

                health = await client.get(f"{url}/health")
                health.raise_for_status()
                return ConnectionTestResult(
                    success=True,
                    version="llama.cpp",
                    latency_ms=self._latency_ms(start),
                )
        except httpx.ConnectError:
            return ConnectionTestResult(success=False, error="Connection refused. Is the runtime running?")
        except httpx.TimeoutException:
            return ConnectionTestResult(success=False, error="Connection timed out after 10 seconds.")
        except httpx.HTTPStatusError as exc:
            return ConnectionTestResult(success=False, error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return ConnectionTestResult(success=False, error=str(exc))

    async def run_discovery(self, runtime: RuntimeConfig) -> DiscoveryResult:
        checks: list[DiscoveryCheck] = []

        if runtime.type == "lemonade":
            checks.extend(await self._discover_lemonade(runtime))
        elif runtime.type == "ollama":
            checks.extend(await self._discover_ollama(runtime))
        elif runtime.type == "llamacpp":
            checks.extend(await self._discover_llamacpp(runtime))
        else:
            checks.append(DiscoveryCheck(name="Runtime type", endpoint=runtime.type, status="skip", detail="Custom runtime"))

        checks.extend(self._local_system_checks())
        passed = sum(1 for check in checks if check.status == "ok")
        capabilities = {
            check.name.lower().replace(" ", "_").replace(".", ""): check.status == "ok"
            for check in checks
        }

        return DiscoveryResult(
            checks=checks,
            total=len(checks),
            passed=passed,
            capabilities_json=capabilities,
        )

    async def discover_lemonade_servers(self, listen_ms: int = 2500) -> LemonadeDiscoveryResponse:
        """Discover Lemonade servers through UDP beacons and conservative HTTP probes."""
        listen_ms = max(250, min(listen_ms, 5000))
        candidates: dict[str, LemonadeDiscoveryCandidate] = {}

        for candidate in await self._listen_for_lemonade_beacons(listen_ms):
            candidates[candidate.url] = candidate

        fallback_results = await asyncio.gather(
            *(self._probe_lemonade_candidate(url, source="http_fallback") for url in LEMONADE_FALLBACK_URLS),
            return_exceptions=True,
        )
        for result in fallback_results:
            if isinstance(result, LemonadeDiscoveryCandidate) and result.reachable:
                candidates.setdefault(result.url, result)

        ordered = sorted(
            candidates.values(),
            key=lambda item: (
                0 if item.source == "udp_beacon" else 1,
                0 if item.reachable else 1,
                item.name.lower(),
                item.url,
            ),
        )
        return LemonadeDiscoveryResponse(candidates=ordered, total=len(ordered), udp_listen_ms=listen_ms)

    async def connection_doctor(self, runtime: RuntimeConfig) -> ConnectionDoctorResponse:
        """Run an operator-focused diagnosis for a configured runtime."""
        normalized_url = _normalize_lemonade_url(runtime.url)
        local_target = _is_local_url(normalized_url)
        checks: list[ConnectionDoctorCheck] = []
        warnings: list[str] = []

        response = ConnectionDoctorResponse(
            runtime_id=runtime.id,
            target_url=runtime.url,
            normalized_url=normalized_url,
            local_target=local_target,
        )

        if runtime.type != "lemonade":
            response.warnings.append("Only Lemonade runtimes are fully supported by Connection Doctor today.")
            response.recommended_next_action = "Use the runtime-specific test action for this prepared runtime."
            return response

        if not normalized_url:
            checks.append(ConnectionDoctorCheck(name="URL", status="error", detail="Runtime URL is empty."))
            response.checks = checks
            response.warnings.append("Set a Lemonade server URL before running diagnostics.")
            response.recommended_next_action = "Enter a Lemonade URL such as http://localhost:13305."
            return response

        start = time.monotonic()
        health_data: dict = {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                health = await client.get(f"{normalized_url}/api/v1/health")
                health.raise_for_status()
                health_data = health.json()
            response.reachable = True
            response.api_available = True
            response.version = str(health_data.get("version") or "unknown")
            response.status = str(health_data.get("status") or "unknown")
            response.loaded_model = _loaded_model_name(health_data)
            telemetry = health_data.get("telemetry")
            if isinstance(telemetry, dict) and isinstance(telemetry.get("enabled"), bool):
                response.telemetry_enabled = telemetry["enabled"]
            checks.append(
                ConnectionDoctorCheck(
                    name="Lemonade health",
                    status="ok",
                    detail=f"{response.status} · {response.version} · {self._latency_ms(start)}ms",
                )
            )
        except httpx.ConnectError:
            checks.append(ConnectionDoctorCheck(name="Lemonade health", status="error", detail="Connection refused."))
            warnings.append("Lemonade is not reachable at the configured URL.")
        except httpx.TimeoutException:
            checks.append(ConnectionDoctorCheck(name="Lemonade health", status="error", detail="Health request timed out."))
            warnings.append("The Lemonade server did not respond before timeout.")
        except httpx.HTTPStatusError as exc:
            checks.append(ConnectionDoctorCheck(name="Lemonade health", status="error", detail=f"HTTP {exc.response.status_code}"))
            warnings.append("The configured URL responded, but not with a healthy Lemonade response.")
        except Exception as exc:
            checks.append(ConnectionDoctorCheck(name="Lemonade health", status="error", detail=str(exc)))
            warnings.append("Unexpected error while checking Lemonade health.")

        if response.reachable:
            if response.loaded_model:
                checks.append(ConnectionDoctorCheck(name="Loaded model", status="ok", detail=response.loaded_model))
            else:
                checks.append(ConnectionDoctorCheck(name="Loaded model", status="warning", detail="No model is currently loaded."))
                warnings.append("No model is loaded. This is fine for setup, but clients cannot generate until a model is loaded.")

        if local_target:
            response.host_telemetry_available = True
            checks.append(ConnectionDoctorCheck(name="Host telemetry", status="ok", detail="Target appears local; LCC host telemetry is applicable."))
            llama = find_llama_server()
            if llama.found:
                response.process_evidence = "found"
                checks.append(ConnectionDoctorCheck(name="Process evidence", status="ok", detail=f"llama-server PID {llama.process.pid if llama.process else 'unknown'} found."))
            else:
                response.process_evidence = "not_running"
                checks.append(ConnectionDoctorCheck(name="Process evidence", status="warning", detail="No llama-server process found. This is expected when no model is loaded."))
        else:
            response.host_telemetry_available = False
            response.process_evidence = "unavailable"
            checks.append(ConnectionDoctorCheck(name="Host telemetry", status="warning", detail="Target is remote; local LCC process/RAM/systemd data may not describe that server."))
            warnings.append("This target looks remote. API checks are valid, but host telemetry only describes the LCC host unless a collector is added.")

        if runtime.admin_key:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                    config = await client.get(f"{normalized_url}/internal/config", headers=self._admin_headers(runtime.admin_key))
                if config.status_code == 200:
                    response.admin_config_available = True
                    checks.append(ConnectionDoctorCheck(name="Admin config", status="ok", detail="Admin config endpoint reachable."))
                else:
                    checks.append(ConnectionDoctorCheck(name="Admin config", status="warning", detail=f"HTTP {config.status_code}"))
                    warnings.append("Admin key is configured, but Lemonade did not accept it for internal config.")
            except Exception as exc:
                checks.append(ConnectionDoctorCheck(name="Admin config", status="warning", detail=str(exc)))
                warnings.append("Admin config check failed.")
        else:
            checks.append(ConnectionDoctorCheck(name="Admin config", status="skip", detail="No Lemonade admin API key configured."))

        if capabilities.cmd_systemctl and local_target:
            checks.append(ConnectionDoctorCheck(name="systemd", status="ok", detail="systemctl is available for local service checks."))
        elif local_target:
            checks.append(ConnectionDoctorCheck(name="systemd", status="skip", detail="systemctl capability is not available."))

        response.checks = checks
        response.warnings = warnings
        response.recommended_next_action = _connection_doctor_next_action(response)
        return response

    def complete_setup(self, request: CompleteSetupRequest) -> LccConfigPublic:
        runtime = request.runtime
        runtime.is_active = True
        config = LccConfig(
            setup_complete=True,
            setup_date=datetime.now(timezone.utc),
            runtimes=[runtime],
            active_runtime_id=runtime.id,
            system=request.system,
            appearance=request.appearance,
        )
        self.save_config(config)
        return self._redact(config)

    def update_system(self, system: SystemConfig) -> LccConfigPublic:
        config = self.get_config()
        config.system = system
        self.save_config(config)
        return self._redact(config)

    def update_appearance(self, appearance: AppearanceConfig) -> LccConfigPublic:
        config = self.get_config()
        config.appearance = appearance
        self.save_config(config)
        return self._redact(config)

    def add_runtime(self, runtime: RuntimeConfig) -> RuntimeConfigPublic:
        config = self.get_config()
        if any(item.id == runtime.id for item in config.runtimes):
            raise ValueError(f"Runtime '{runtime.id}' already exists")
        config.runtimes.append(runtime)
        self.save_config(config)
        return self._redact_runtime(runtime)

    def update_runtime(self, runtime_id: str, runtime: RuntimeConfig) -> RuntimeConfigPublic | None:
        config = self.get_config()
        for index, current in enumerate(config.runtimes):
            if current.id == runtime_id:
                runtime.id = runtime_id
                runtime.is_active = current.is_active
                if runtime.admin_key is None:
                    runtime.admin_key = current.admin_key
                config.runtimes[index] = runtime
                self.save_config(config)
                return self._redact_runtime(runtime)
        return None

    def remove_runtime(self, runtime_id: str) -> bool:
        config = self.get_config()
        if len(config.runtimes) <= 1:
            raise ValueError("At least one runtime must remain configured.")
        before = len(config.runtimes)
        config.runtimes = [runtime for runtime in config.runtimes if runtime.id != runtime_id]
        if before == len(config.runtimes):
            return False
        if config.active_runtime_id == runtime_id:
            config.runtimes[0].is_active = True
            config.active_runtime_id = config.runtimes[0].id
        self.save_config(config)
        return True

    def activate_runtime(self, runtime_id: str) -> RuntimeConfig | None:
        config = self.get_config()
        selected: RuntimeConfig | None = None
        for runtime in config.runtimes:
            runtime.is_active = runtime.id == runtime_id
            if runtime.is_active:
                selected = runtime
        if selected is None:
            return None
        config.active_runtime_id = runtime_id
        self.save_config(config)
        return selected

    async def test_saved_runtime(self, runtime_id: str) -> ConnectionTestResult | None:
        config = self.get_config()
        for runtime in config.runtimes:
            if runtime.id != runtime_id:
                continue
            if runtime.type == "custom":
                return ConnectionTestResult(success=False, error="Custom runtime testing is not implemented.")
            result = await self.test_connection(
                SetupConnectionRequest(type=runtime.type, url=runtime.url, admin_key=runtime.admin_key)
            )
            runtime.last_tested = datetime.now(timezone.utc)
            runtime.test_status = "ok" if result.success else "error"
            self.save_config(config)
            return result
        return None

    async def discover_saved_runtime(self, runtime_id: str) -> DiscoveryResult | None:
        config = self.get_config()
        for runtime in config.runtimes:
            if runtime.id != runtime_id:
                continue
            result = await self.run_discovery(runtime)
            runtime.capabilities_count = result.passed
            self.save_config(config)
            return result
        return None

    def _default_config(self) -> LccConfig:
        return LccConfig(
            runtimes=[
                RuntimeConfig(
                    id="lemonade-local",
                    type="lemonade",
                    name="Local Lemonade",
                    url=settings.lemonade_url,
                    is_active=True,
                )
            ],
            active_runtime_id="lemonade-local",
        )

    async def _discover_lemonade(self, runtime: RuntimeConfig) -> list[DiscoveryCheck]:
        headers = self._admin_headers(runtime.admin_key)
        endpoints = [
            ("Health", "/api/v1/health"),
            ("Models list", "/api/tags"),
            ("Running models", "/api/ps"),
            ("System info", "/api/v1/system-info"),
            ("Stats", "/api/v1/stats"),
        ]
        checks = await self._check_http_endpoints(runtime.url, endpoints, headers=headers)
        if runtime.admin_key:
            checks.extend(await self._check_lemonade_admin_endpoints(runtime.url, headers))
        return checks

    async def _listen_for_lemonade_beacons(self, listen_ms: int) -> list[LemonadeDiscoveryCandidate]:
        loop = asyncio.get_running_loop()
        protocol = _LemonadeBeaconProtocol()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", LEMONADE_BEACON_PORT))
            transport, _ = await loop.create_datagram_endpoint(lambda: protocol, sock=sock)
        except OSError:
            sock.close()
            return []

        try:
            await asyncio.sleep(listen_ms / 1000)
        finally:
            transport.close()

        candidates: list[LemonadeDiscoveryCandidate] = []
        for payload, address in protocol.payloads:
            candidate = self._candidate_from_beacon(payload, address)
            if candidate:
                enriched = await self._probe_lemonade_candidate(candidate.url, source="udp_beacon", hostname=candidate.hostname)
                candidates.append(enriched if enriched else candidate)
        return candidates

    def _candidate_from_beacon(self, payload: dict, address: tuple[str, int]) -> LemonadeDiscoveryCandidate | None:
        if payload.get("service") != "lemonade":
            return None
        url = _normalize_lemonade_url(str(payload.get("url") or ""))
        if not url:
            host = address[0]
            url = f"http://{host}:13305"
        hostname = str(payload.get("hostname") or address[0])
        return LemonadeDiscoveryCandidate(
            name=hostname,
            url=url,
            source="udp_beacon",
            hostname=hostname,
            detail="Lemonade UDP beacon",
        )

    async def _probe_lemonade_candidate(
        self,
        url: str,
        *,
        source: Literal["udp_beacon", "http_fallback", "manual"],
        hostname: str | None = None,
    ) -> LemonadeDiscoveryCandidate | None:
        root_url = _normalize_lemonade_url(url)
        if not root_url:
            return None

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(1.25)) as client:
                health = await client.get(f"{root_url}/api/v1/health")
                health.raise_for_status()
                data = health.json()
        except Exception:
            return None

        latency_ms = self._latency_ms(start)
        detected_hostname = hostname or root_url.removeprefix("http://").removeprefix("https://").split(":", 1)[0]
        return LemonadeDiscoveryCandidate(
            name=detected_hostname,
            url=root_url,
            source=source,
            reachable=True,
            hostname=detected_hostname,
            version=str(data.get("version") or "unknown"),
            status=str(data.get("status") or "unknown"),
            model_loaded=_loaded_model_name(data),
            latency_ms=latency_ms,
            detail="Health endpoint reachable",
        )

    async def _discover_ollama(self, runtime: RuntimeConfig) -> list[DiscoveryCheck]:
        return await self._check_http_endpoints(
            runtime.url,
            [("Version", "/api/version"), ("Models list", "/api/tags"), ("Running models", "/api/ps")],
        )

    async def _discover_llamacpp(self, runtime: RuntimeConfig) -> list[DiscoveryCheck]:
        return await self._check_http_endpoints(
            runtime.url,
            [("Health", "/health"), ("Models", "/v1/models"), ("Slots", "/slots"), ("Metrics", "/metrics")],
        )

    async def _check_http_endpoints(
        self,
        base_url: str,
        endpoints: list[tuple[str, str]],
        *,
        headers: dict[str, str] | None = None,
    ) -> list[DiscoveryCheck]:
        checks: list[DiscoveryCheck] = []
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            for name, path in endpoints:
                endpoint = f"{url}{path}"
                try:
                    response = await client.get(endpoint, headers=headers)
                    checks.append(
                        DiscoveryCheck(
                            name=name,
                            endpoint=path,
                            status="ok" if response.status_code == 200 else "warning",
                            detail=f"HTTP {response.status_code}",
                        )
                    )
                except Exception as exc:
                    checks.append(DiscoveryCheck(name=name, endpoint=path, status="error", detail=str(exc)))
        return checks

    async def _check_lemonade_admin_endpoints(
        self,
        base_url: str,
        headers: dict[str, str] | None,
    ) -> list[DiscoveryCheck]:
        checks: list[DiscoveryCheck] = []
        url = base_url.rstrip("/")

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            try:
                config_response = await client.get(f"{url}/internal/config", headers=headers)
            except Exception as exc:
                detail = str(exc)
                checks.append(DiscoveryCheck(name="Internal config", endpoint="/internal/config", status="error", detail=detail))
                checks.append(DiscoveryCheck(name="Internal set", endpoint="/internal/set", status="skip", detail="Skipped because config check failed."))
                return checks

            checks.append(
                DiscoveryCheck(
                    name="Internal config",
                    endpoint="/internal/config",
                    status="ok" if config_response.status_code == 200 else "warning",
                    detail=f"HTTP {config_response.status_code}",
                )
            )

            if config_response.status_code != 200:
                checks.append(
                    DiscoveryCheck(
                        name="Internal set",
                        endpoint="/internal/set",
                        status="skip",
                        detail=f"Skipped because /internal/config returned HTTP {config_response.status_code}.",
                    )
                )
                return checks

            try:
                current_config = config_response.json()
            except ValueError:
                checks.append(
                    DiscoveryCheck(
                        name="Internal set",
                        endpoint="/internal/set",
                        status="skip",
                        detail="Skipped because /internal/config did not return JSON.",
                    )
                )
                return checks

            noop_update = self._safe_lemonade_noop_update(current_config)
            if not noop_update:
                checks.append(
                    DiscoveryCheck(
                        name="Internal set",
                        endpoint="/internal/set",
                        status="skip",
                        detail="No safe scalar config value found for a no-op write check.",
                    )
                )
                return checks

            try:
                set_response = await client.post(f"{url}/internal/set", json=noop_update, headers=headers)
                detail = f"HTTP {set_response.status_code}"
                if set_response.status_code != 200 and set_response.text:
                    detail = f"{detail}: {set_response.text[:160]}"
                checks.append(
                    DiscoveryCheck(
                        name="Internal set",
                        endpoint="/internal/set",
                        status="ok" if set_response.status_code == 200 else "warning",
                        detail=detail,
                    )
                )
            except Exception as exc:
                checks.append(DiscoveryCheck(name="Internal set", endpoint="/internal/set", status="error", detail=str(exc)))

        return checks

    def _safe_lemonade_noop_update(self, current_config: dict) -> dict:
        for key in ("global_timeout", "ctx_size", "log_level"):
            value = current_config.get(key)
            if isinstance(value, (str, int, float)):
                return {key: value}
        return {}

    def _local_system_checks(self) -> list[DiscoveryCheck]:
        checks: list[DiscoveryCheck] = []
        try:
            import psutil

            psutil.virtual_memory()
            checks.append(DiscoveryCheck(name="Hardware sensors", endpoint="psutil", status="ok", detail="Available"))
        except Exception as exc:
            checks.append(DiscoveryCheck(name="Hardware sensors", endpoint="psutil", status="error", detail=str(exc)))

        checks.append(self._command_check("Service status", "systemctl", ["systemctl", "--version"]))
        checks.append(self._command_check("Journal logs", "journalctl", ["journalctl", "--version"]))
        checks.append(DiscoveryCheck(name="Process cmdline", endpoint="/proc/PID/cmdline", status="skip", detail="Checked when process exists"))
        return checks

    def _command_check(self, name: str, endpoint: str, command: list[str]) -> DiscoveryCheck:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
            status = "ok" if result.returncode == 0 else "warning"
            detail = (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else "No output"
            return DiscoveryCheck(name=name, endpoint=endpoint, status=status, detail=detail[:200])
        except Exception as exc:
            return DiscoveryCheck(name=name, endpoint=endpoint, status="error", detail=str(exc))

    async def _count_lemonade_models(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str] | None,
    ) -> int:
        try:
            response = await client.get(f"{url}/api/tags", headers=headers)
            if response.status_code != 200:
                return 0
            return len(response.json().get("models", []))
        except Exception:
            return 0

    def _redact(self, config: LccConfig) -> LccConfigPublic:
        return LccConfigPublic(
            setup_complete=config.setup_complete,
            setup_date=config.setup_date,
            version=config.version,
            runtimes=[self._redact_runtime(runtime) for runtime in config.runtimes],
            active_runtime_id=config.active_runtime_id,
            system=config.system,
            appearance=config.appearance,
        )

    def _redact_runtime(self, runtime: RuntimeConfig) -> RuntimeConfigPublic:
        return RuntimeConfigPublic(
            id=runtime.id,
            type=runtime.type,
            name=runtime.name,
            url=runtime.url,
            admin_key_configured=bool(runtime.admin_key),
            is_active=runtime.is_active,
            access_mode=runtime.access_mode,
            capabilities_count=runtime.capabilities_count,
            last_tested=runtime.last_tested,
            test_status=runtime.test_status,
        )

    def _admin_headers(self, admin_key: str | None) -> dict[str, str] | None:
        if not admin_key:
            return None
        return {"Authorization": f"Bearer {admin_key}"}

    def _latency_ms(self, start: float) -> float:
        return round((time.monotonic() - start) * 1000, 1)


class _LemonadeBeaconProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.payloads: list[tuple[dict, tuple[str, int]]] = []

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if isinstance(payload, dict):
            self.payloads.append((payload, addr))


def _normalize_lemonade_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    for suffix in ("/api/v1", "/v1"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url.rstrip("/")


def _is_local_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        local_names = {socket.gethostname().lower(), socket.getfqdn().lower()}
    except OSError:
        local_names = set()
    return host in local_names


def _loaded_model_name(data: dict) -> str | None:
    model_loaded = data.get("model_loaded")
    if isinstance(model_loaded, str) and model_loaded:
        return model_loaded

    loaded = data.get("all_models_loaded") or data.get("loaded_models") or data.get("models")
    if isinstance(loaded, list) and loaded:
        first = loaded[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            value = first.get("name") or first.get("model") or first.get("id")
            return str(value) if value else None
    return None


def _connection_doctor_next_action(response: ConnectionDoctorResponse) -> str:
    if not response.reachable:
        return "Fix the Lemonade URL or start Lemonade, then run Connection Doctor again."
    if not response.local_target:
        return "Use API health for this remote target; do not trust local host telemetry for the remote server."
    if response.loaded_model:
        return "Connection is usable. Inspect process evidence or run a smoke test if you need runtime proof."
    return "Connection is healthy. Load a model when you are ready to serve clients."
