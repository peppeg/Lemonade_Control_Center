"""First-run setup and persistent application settings."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.models.setup import (
    AppearanceConfig,
    CompleteSetupRequest,
    ConnectionTestResult,
    DiscoveryCheck,
    DiscoveryResult,
    LccConfig,
    LccConfigPublic,
    RuntimeConfig,
    RuntimeConfigPublic,
    SetupConnectionRequest,
    SystemConfig,
)

CONFIG_FILE = Path(__file__).parent.parent / "data" / "config.json"


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
                    url="http://localhost:13305",
                    is_active=True,
                )
            ],
            active_runtime_id="lemonade-local",
        )

    async def _discover_lemonade(self, runtime: RuntimeConfig) -> list[DiscoveryCheck]:
        headers = self._admin_headers(runtime.admin_key)
        endpoints = [
            ("Health", "/api/v1/health"),
            ("Models list", "/api/v1/tags"),
            ("Running models", "/api/v1/ps"),
            ("System info", "/api/v1/system-info"),
            ("Stats", "/api/v1/stats"),
        ]
        if runtime.admin_key:
            endpoints.extend([
                ("Internal config", "/internal/config"),
                ("Internal set", "/internal/set"),
            ])
        return await self._check_http_endpoints(runtime.url, endpoints, headers=headers)

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
            response = await client.get(f"{url}/api/v1/tags", headers=headers)
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
