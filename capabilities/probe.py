#!/usr/bin/env python3
"""
Lemonade Control Center — Capabilities Probe

Testa tutti gli endpoint Lemonade e i comandi di sistema disponibili.
Salva i risultati in capabilities/results/ e genera CAPABILITIES.md.

Uso:
  cd capabilities
  python probe.py                          # probe base
  python probe.py --admin-key YOUR_KEY     # probe con admin API
  python probe.py --lemonade-url HOST:PORT # URL custom
  python probe.py --output-dir ./results   # directory output custom
"""

import argparse
import asyncio
import json
import subprocess
import sys
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum

# Unica dipendenza esterna (httpx deve essere installato separatamente)
try:
    import httpx
except ImportError:
    print("ERROR: httpx non installato. Esegui: pip install httpx")
    sys.exit(1)


@dataclass
class ProbeConfig:
    lemonade_url: str = "http://localhost:13305"
    admin_key: str | None = None
    output_dir: Path = Path("results")
    timeout: float = 10.0  # timeout per singola richiesta


class ProbeStatus(Enum):
    OK = "ok"              # 2xx
    NOT_FOUND = "not_found"  # 404
    UNAUTHORIZED = "unauthorized"  # 401/403
    ERROR = "error"        # 5xx o connection error
    TIMEOUT = "timeout"    # timeout
    SKIPPED = "skipped"    # non testato (es. delete)


@dataclass
class EndpointResult:
    endpoint: str
    method: str
    status: ProbeStatus
    status_code: int | None = None
    response_time_ms: float | None = None
    response_file: str | None = None
    notes: str = ""
    works: bool = False


@dataclass
class CommandResult:
    command: str
    status: ProbeStatus
    exit_code: int | None = None
    output_preview: str = ""   # prime 5 righe
    notes: str = ""
    works: bool = False


@dataclass
class ProbeSummary:
    probe_timestamp: str
    lemonade_url: str
    lemonade_version: str | None = None
    admin_key_configured: bool = False
    endpoints: dict[str, EndpointResult] = field(default_factory=dict)
    system_commands: dict[str, CommandResult] = field(default_factory=dict)
    websocket: dict = field(default_factory=dict)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def save_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


async def probe_endpoint(
    client: httpx.AsyncClient,
    config: ProbeConfig,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    headers: dict | None = None,
    save_as: str | None = None,
    skip: bool = False,
    skip_reason: str = "",
    notes: str = ""
) -> EndpointResult:
    """Testa un singolo endpoint e salva la response."""

    if skip:
        return EndpointResult(
            endpoint=path, method=method,
            status=ProbeStatus.SKIPPED,
            notes=skip_reason
        )

    url = f"{config.lemonade_url}{path}"
    start = time.monotonic()

    try:
        if method == "GET":
            resp = await client.get(url, headers=headers, timeout=config.timeout)
        else:
            resp = await client.post(url, json=body, headers=headers, timeout=config.timeout)

        elapsed = (time.monotonic() - start) * 1000

        # Salva response se richiesto
        response_file = None
        if save_as and resp.status_code < 500:
            response_file = f"results/{save_as}"
            # Salva come JSON se possibile, altrimenti testo
            try:
                data = resp.json()
                save_json(config.output_dir / save_as, data)
            except:
                save_text(config.output_dir / save_as, resp.text)

        # Determina status
        if 200 <= resp.status_code < 300:
            status = ProbeStatus.OK
        elif resp.status_code == 404:
            status = ProbeStatus.NOT_FOUND
        elif resp.status_code in (401, 403):
            status = ProbeStatus.UNAUTHORIZED
        else:
            status = ProbeStatus.ERROR

        return EndpointResult(
            endpoint=path, method=method,
            status=status,
            status_code=resp.status_code,
            response_time_ms=round(elapsed, 1),
            response_file=response_file,
            works=(status == ProbeStatus.OK),
            notes=notes
        )

    except httpx.TimeoutException:
        return EndpointResult(
            endpoint=path, method=method,
            status=ProbeStatus.TIMEOUT,
            notes="Request timed out"
        )
    except httpx.ConnectError:
        return EndpointResult(
            endpoint=path, method=method,
            status=ProbeStatus.ERROR,
            notes="Connection refused — Lemonade non raggiungibile"
        )


def probe_command(command: str, *, timeout: float = 10.0) -> CommandResult:
    """Esegue un comando di sistema e cattura il risultato."""
    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True,
            timeout=timeout
        )

        preview = "\n".join(result.stdout.strip().split("\n")[:5])

        return CommandResult(
            command=command,
            status=ProbeStatus.OK if result.returncode == 0 else ProbeStatus.ERROR,
            exit_code=result.returncode,
            output_preview=preview,
            works=(result.returncode == 0),
            notes=result.stderr.strip()[:200] if result.returncode != 0 else ""
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            command=command,
            status=ProbeStatus.TIMEOUT,
            notes="Command timed out"
        )
    except FileNotFoundError:
        return CommandResult(
            command=command,
            status=ProbeStatus.ERROR,
            notes="Command not found"
        )


def find_llama_server_pid() -> int | None:
    """Trova il PID del processo llama-server."""
    try:
        result = subprocess.run(
            "pgrep -f llama-server | head -1",
            shell=True, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except:
        pass
    return None


async def probe_websocket(base_url: str, ws_port: int) -> dict:
    """Testa la connessione WebSocket."""
    try:
        import websockets
        ws_url = f"ws://localhost:{ws_port}"
        async with websockets.connect(ws_url, open_timeout=5) as ws:
            # Aspetta un messaggio per max 3 secondi
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                return {
                    "status": "ok",
                    "port": ws_port,
                    "url": ws_url,
                    "sample_message_type": type(msg).__name__,
                    "sample_message_preview": str(msg)[:200]
                }
            except asyncio.TimeoutError:
                return {
                    "status": "ok_no_data",
                    "port": ws_port,
                    "url": ws_url,
                    "notes": "Connesso ma nessun messaggio ricevuto in 3s"
                }
    except ImportError:
        return {
            "status": "skipped",
            "notes": "websockets library non installata (pip install websockets)"
        }
    except Exception as e:
        return {
            "status": "error",
            "port": ws_port,
            "error": str(e)
        }


async def run_probe(config: ProbeConfig) -> ProbeSummary:
    """Esegue il probe completo."""

    summary = ProbeSummary(
        probe_timestamp=datetime.now(timezone.utc).isoformat(),
        lemonade_url=config.lemonade_url,
        admin_key_configured=config.admin_key is not None
    )

    # Headers per admin API
    admin_headers = None
    if config.admin_key:
        admin_headers = {"Authorization": f"Bearer {config.admin_key}"}

    config.output_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient() as client:

        # ═══════════════════════════════════════════════
        # GRUPPO 1: Lemonade Management API
        # ═══════════════════════════════════════════════

        # Health (fondamentale — se questo fallisce, tutto il resto è compromesso)
        health = await probe_endpoint(client, config, "GET", "/api/v1/health",
                                       save_as="health.json")
        summary.endpoints["/api/v1/health"] = health

        # Estrai versione da health se disponibile
        if health.works:
            try:
                health_data = load_json(config.output_dir / "health.json")
                summary.lemonade_version = health_data.get("version")
            except:
                pass

        # Stats
        summary.endpoints["/api/v1/stats"] = await probe_endpoint(
            client, config, "GET", "/api/v1/stats",
            save_as="stats.json")

        # System info
        summary.endpoints["/api/v1/system-info"] = await probe_endpoint(
            client, config, "GET", "/api/v1/system-info",
            save_as="system_info.json")

        # Liveness
        summary.endpoints["/live"] = await probe_endpoint(
            client, config, "GET", "/live",
            save_as="live.json")

        # Load — SOLO se un modello è disponibile e NON loaded
        # (non vogliamo interferire con un modello in uso)
        summary.endpoints["/api/v1/load"] = EndpointResult(
            endpoint="/api/v1/load", method="POST",
            status=ProbeStatus.SKIPPED,
            notes="Skipped: testato manualmente per non interferire con modello in uso"
        )

        # Unload — SOLO probe, NON eseguiamo
        summary.endpoints["/api/v1/unload"] = EndpointResult(
            endpoint="/api/v1/unload", method="POST",
            status=ProbeStatus.SKIPPED,
            notes="Skipped: non eseguiamo unload automaticamente"
        )

        # Delete — MAI eseguire nel probe
        summary.endpoints["/api/v1/delete"] = EndpointResult(
            endpoint="/api/v1/delete", method="POST",
            status=ProbeStatus.SKIPPED,
            notes="Skipped: azione distruttiva, mai eseguire nel probe"
        )

        # Pull — MAI eseguire nel probe (scaricherebbe un modello)
        summary.endpoints["/api/v1/pull"] = EndpointResult(
            endpoint="/api/v1/pull", method="POST",
            status=ProbeStatus.SKIPPED,
            notes="Skipped: scaricherebbe un modello, testare manualmente"
        )

        # ═══════════════════════════════════════════════
        # GRUPPO 2: Internal API
        # ═══════════════════════════════════════════════

        summary.endpoints["/internal/config"] = await probe_endpoint(
            client, config, "GET", "/internal/config",
            headers=admin_headers,
            save_as="internal_config.json",
            skip=(not config.admin_key),
            skip_reason="Admin key non configurata")

        # /internal/set — test con parametro innocuo (lettura log_level)
        summary.endpoints["/internal/set"] = await probe_endpoint(
            client, config, "POST", "/internal/set",
            headers=admin_headers,
            body={"log_level": "info"},  # parametro innocuo, non cambia nulla
            save_as="internal_set_test.json",
            skip=(not config.admin_key),
            skip_reason="Admin key non configurata",
            notes="Test con log_level=info (valore presumibilmente già impostato)")

        summary.endpoints["/internal/cleanup-cache"] = await probe_endpoint(
            client, config, "POST", "/internal/cleanup-cache",
            headers=admin_headers,
            save_as=None,  # non salvare, solo verificare risposta
            skip=(not config.admin_key),
            skip_reason="Admin key non configurata")

        # ═══════════════════════════════════════════════
        # GRUPPO 3: Ollama-Compatible API
        # ═══════════════════════════════════════════════

        summary.endpoints["/api/tags"] = await probe_endpoint(
            client, config, "GET", "/api/tags",
            save_as="models_tags.json")

        summary.endpoints["/api/ps"] = await probe_endpoint(
            client, config, "GET", "/api/ps",
            save_as="models_ps.json")

        summary.endpoints["/api/version"] = await probe_endpoint(
            client, config, "GET", "/api/version",
            save_as="version.json")

        # /api/show — richiede un nome modello
        # Proviamo con il primo modello da /api/tags se disponibile
        show_model_name = None
        tags_result = summary.endpoints.get("/api/tags")
        if tags_result and tags_result.works:
            try:
                tags_data = load_json(config.output_dir / "models_tags.json")
                models = tags_data.get("models", [])
                if models:
                    show_model_name = models[0].get("name") or models[0].get("model")
            except:
                pass

        summary.endpoints["/api/show"] = await probe_endpoint(
            client, config, "POST", "/api/show",
            body={"name": show_model_name} if show_model_name else {"name": "test"},
            save_as="show_model.json",
            notes=f"Testato con modello: {show_model_name}" if show_model_name else "Nessun modello disponibile per il test")

        # ═══════════════════════════════════════════════
        # GRUPPO 4: OpenAI-Compatible API
        # ═══════════════════════════════════════════════

        summary.endpoints["/api/v1/models"] = await probe_endpoint(
            client, config, "GET", "/api/v1/models",
            save_as="models_openai.json")

        # ═══════════════════════════════════════════════
        # GRUPPO 5: WebSocket
        # ═══════════════════════════════════════════════

        ws_port = None
        if health.works:
            try:
                health_data = load_json(config.output_dir / "health.json")
                ws_port = health_data.get("websocket_port")
            except:
                pass

        if ws_port:
            summary.websocket = await probe_websocket(config.lemonade_url, ws_port)
        else:
            summary.websocket = {
                "status": "skipped",
                "notes": "websocket_port non trovata in /api/v1/health"
            }

    # ═══════════════════════════════════════════════
    # GRUPPO 6: Comandi di sistema
    # ═══════════════════════════════════════════════

    system_commands = {
        "lemonade_config": "lemonade config",
        "lemonade_list": "lemonade list --downloaded",
        "lemonade_status": "lemonade status",
        "systemctl_status": "systemctl status lemond.service --no-pager",
        "journalctl_recent": "journalctl -u lemond.service -n 50 -o cat --no-pager",
        "free": "free -h",
        "df_models": "df -h /opt/var/lib/lemonade 2>/dev/null || df -h $HOME/.cache/lemonade 2>/dev/null || df -h /",
        "sensors": "sensors 2>/dev/null || echo 'sensors not available'",
        "du_cache": "du -sh $HOME/.cache/lemonade 2>/dev/null || du -sh /opt/var/lib/lemonade/.cache 2>/dev/null || echo 'cache dir not found'",
    }

    # Trova PID llama-server per probe /proc
    llama_pid = find_llama_server_pid()
    if llama_pid:
        system_commands["proc_cmdline"] = f"tr '\\0' ' ' < /proc/{llama_pid}/cmdline"
        system_commands["proc_status"] = f"cat /proc/{llama_pid}/status | head -20"
    else:
        system_commands["proc_cmdline"] = "echo 'llama-server PID not found'"

    for key, cmd in system_commands.items():
        summary.system_commands[key] = probe_command(cmd)

    # Salva tutti i risultati dei comandi in un unico file
    save_json(config.output_dir / "system_commands.json", {
        key: {
            "command": r.command,
            "works": r.works,
            "exit_code": r.exit_code,
            "output": r.output_preview,
            "notes": r.notes
        }
        for key, r in summary.system_commands.items()
    })

    return summary


def generate_capabilities_md(summary: ProbeSummary) -> str:
    """Genera CAPABILITIES.md dal probe summary."""

    lines = [
        f"# 🍋 Lemonade Capabilities — Probe Results",
        f"",
        f"> Auto-generated by `probe.py` on {summary.probe_timestamp}",
        f"> Lemonade URL: `{summary.lemonade_url}`",
        f"> Lemonade Version: `{summary.lemonade_version or 'unknown'}`",
        f"> Admin API Key: {'✅ configured' if summary.admin_key_configured else '❌ not configured'}",
        f"",
        f"---",
        f"",
        f"## Endpoint Status",
        f"",
        f"| Endpoint | Method | Status | Code | Time (ms) | Works | Notes |",
        f"|---|---|---|---|---|---|---|",
    ]

    for path, r in summary.endpoints.items():
        status_icon = {
            ProbeStatus.OK: "✅",
            ProbeStatus.NOT_FOUND: "❌ 404",
            ProbeStatus.UNAUTHORIZED: "🔒 Auth",
            ProbeStatus.ERROR: "❌ Error",
            ProbeStatus.TIMEOUT: "⏰ Timeout",
            ProbeStatus.SKIPPED: "⏭ Skipped",
        }.get(r.status, "?")

        lines.append(
            f"| `{path}` | {r.method} | {status_icon} | "
            f"{r.status_code or '-'} | {r.response_time_ms or '-'} | "
            f"{'✅' if r.works else '❌'} | {r.notes} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## System Commands",
        f"",
        f"| Command | Works | Exit Code | Notes |",
        f"|---|---|---|---|",
    ]

    for key, r in summary.system_commands.items():
        lines.append(
            f"| `{r.command[:60]}` | "
            f"{'✅' if r.works else '❌'} | {r.exit_code or '-'} | {r.notes[:80]} |"
        )

    # WebSocket
    lines += [
        f"",
        f"---",
        f"",
        f"## WebSocket",
        f"",
        f"```json",
        f"{json.dumps(summary.websocket, indent=2)}",
        f"```",
    ]

    # Capabilities summary per il backend
    lines += [
        f"",
        f"---",
        f"",
        f"## Capabilities Map (per backend LCC)",
        f"",
        f"Copia questo blocco nel `.env` del backend come reference:",
        f"",
        f"```env",
        f"# Auto-generated capabilities — {summary.probe_timestamp}",
    ]

    cap_map = {
        "health": summary.endpoints.get("/api/v1/health", EndpointResult("/api/v1/health", "GET", ProbeStatus.ERROR)).works,
        "stats": summary.endpoints.get("/api/v1/stats", EndpointResult("/api/v1/stats", "GET", ProbeStatus.ERROR)).works,
        "system_info": summary.endpoints.get("/api/v1/system-info", EndpointResult("/api/v1/system-info", "GET", ProbeStatus.ERROR)).works,
        "load": True,  # Always available (skipped in probe but fundamental)
        "unload": True,
        "delete": True,  # Available but protected by ENABLE_DELETE
        "internal_config": summary.endpoints.get("/internal/config", EndpointResult("/internal/config", "GET", ProbeStatus.ERROR)).works,
        "internal_set": summary.endpoints.get("/internal/set", EndpointResult("/internal/set", "POST", ProbeStatus.ERROR)).works,
        "ollama_tags": summary.endpoints.get("/api/tags", EndpointResult("/api/tags", "GET", ProbeStatus.ERROR)).works,
        "ollama_ps": summary.endpoints.get("/api/ps", EndpointResult("/api/ps", "GET", ProbeStatus.ERROR)).works,
        "ollama_show": summary.endpoints.get("/api/show", EndpointResult("/api/show", "POST", ProbeStatus.ERROR)).works,
        "ollama_version": summary.endpoints.get("/api/version", EndpointResult("/api/version", "GET", ProbeStatus.ERROR)).works,
        "openai_models": summary.endpoints.get("/api/v1/models", EndpointResult("/api/v1/models", "GET", ProbeStatus.ERROR)).works,
    }

    for key, val in cap_map.items():
        lines.append(f"CAP_{key.upper()}={'true' if val else 'false'}")

    lines += [
        f"```",
        f"",
        f"---",
        f"",
        f"## How to Re-run",
        f"",
        f"```bash",
        f"cd capabilities",
        f"python probe.py --lemonade-url {summary.lemonade_url}",
        f"```",
    ]

    return "\n".join(lines)


def print_summary(summary: ProbeSummary):
    """Stampa un riepilogo colorato a console."""
    total = len(summary.endpoints)
    working = sum(1 for e in summary.endpoints.values() if e.works)
    skipped = sum(1 for e in summary.endpoints.values() if e.status == ProbeStatus.SKIPPED)
    failed = total - working - skipped

    print(f"\n{'='*60}")
    print(f"  PROBE RESULTS")
    print(f"  Lemonade: {summary.lemonade_version or 'unknown'}")
    print(f"  Timestamp: {summary.probe_timestamp}")
    print(f"{'='*60}")
    print(f"  Endpoints:  ✅ {working} ok  |  ❌ {failed} failed  |  ⏭ {skipped} skipped")

    cmd_total = len(summary.system_commands)
    cmd_ok = sum(1 for c in summary.system_commands.values() if c.works)
    print(f"  Commands:   ✅ {cmd_ok} ok  |  ❌ {cmd_total - cmd_ok} failed")

    print(f"\n  Output saved to: {Path('results').absolute()}")
    print(f"  Capabilities: CAPABILITIES.md")
    print(f"{'='*60}")

    # Evidenzia problemi
    for path, r in summary.endpoints.items():
        if r.status in (ProbeStatus.ERROR, ProbeStatus.NOT_FOUND):
            print(f"  ⚠  {path}: {r.status.value} ({r.status_code}) {r.notes}")

    for key, r in summary.system_commands.items():
        if not r.works:
            print(f"  ⚠  {r.command}: {r.notes}")


def main():
    parser = argparse.ArgumentParser(
        description="Lemonade Control Center — Capabilities Probe"
    )
    parser.add_argument(
        "--lemonade-url", default="http://localhost:13305",
        help="URL di Lemonade Server (default: http://localhost:13305)"
    )
    parser.add_argument(
        "--admin-key", default=None,
        help="LEMONADE_ADMIN_API_KEY per testare endpoint interni"
    )
    parser.add_argument(
        "--output-dir", default="results",
        help="Directory per i risultati (default: results)"
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0,
        help="Timeout per singola richiesta in secondi (default: 10)"
    )

    args = parser.parse_args()

    # Anche da env var
    admin_key = args.admin_key or os.environ.get("LEMONADE_ADMIN_API_KEY")

    config = ProbeConfig(
        lemonade_url=args.lemonade_url,
        admin_key=admin_key,
        output_dir=Path(args.output_dir),
        timeout=args.timeout
    )

    print(f"🍋 Lemonade Capabilities Probe")
    print(f"   URL: {config.lemonade_url}")
    print(f"   Admin key: {'configured' if config.admin_key else 'not set'}")
    print(f"   Output: {config.output_dir}")
    print()

    # Esegui probe
    summary = asyncio.run(run_probe(config))

    # Salva probe_summary.json
    save_json(config.output_dir / "probe_summary.json", asdict(summary))

    # Genera CAPABILITIES.md
    md = generate_capabilities_md(summary)
    with open("CAPABILITIES.md", "w") as f:
        f.write(md)

    # Stampa riepilogo a console
    print_summary(summary)


if __name__ == "__main__":
    main()
