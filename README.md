# Lemonade Control Center

> A guided graphical operator console for [Lemonade](https://github.com/lemonade-sdk/lemonade), built for Linux inference servers, workstations, and local AI workflows.

[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
![Status](https://img.shields.io/badge/status-active%20development-yellow.svg)
![Platform](https://img.shields.io/badge/platform-Linux-blue.svg)
[![Release](https://img.shields.io/github/v/release/peppeg/Lemonade_Control_Center?display_name=tag)](https://github.com/peppeg/Lemonade_Control_Center/releases/latest)

Lemonade Control Center is an independent, unofficial project. It is not affiliated with, endorsed by, or maintained by the Lemonade project or AMD.

LCC is an unofficial guided operator console for Lemonade. It is not a replacement for the official Lemonade Web UI, not a chat client, and not a model marketplace.

Running local models is the enjoyable part. Operating the server behind them often is not.

I started **Lemonade Control Center (LCC)** because my Lemonade server runs on a Linux AI workstation that I frequently access from another computer through an SSH tunnel. I wanted one place to see what was loaded, understand the settings in use, monitor memory and GPU pressure, inspect failures, and perform routine operations without rebuilding the right terminal command every time. That remote setup is only my own workflow: LCC can be opened directly on the Linux machine that runs it, used through an SSH tunnel, or exposed deliberately on a trusted local network.

LCC is that place: a local graphical operator console for Lemonade.

It is **not a chat interface**. Use Open WebUI, the Lemonade app, or another compatible client to talk to your models. Use LCC to manage and understand the runtime behind them.

## Why LCC?

Lemonade provides a capable server, command-line client, tray application, desktop app, and official web UI. LCC is not meant to replace those official tools. It treats them as the baseline.

LCC exists for a different workflow: operating Lemonade as the backend for local AI tools, coding agents, and Linux inference machines where the important question is not only "which model can I chat with?" but "what is this box doing while my tools hit the server?"

Lemonade runs the models. LCC helps you operate, verify, diagnose, and compare them.

On Linux, `lemond` is also well suited to running as a headless system service. When the inference machine has no display or is managed remotely, desktop tooling is no longer the most convenient operational surface.

The alternative is usually a collection of terminal commands: check the service, inspect the journal, find the active `llama-server` process, monitor memory, load a model with the right options, and remember which settings worked last time.

LCC brings those tasks together without hiding the technical details that matter. Context size, runtime arguments, memory pressure, backend selection, service state, and process behavior remain visible because changing them can have real consequences.

The goal is a low-floor, high-ceiling interface:

- easy enough for a new user to avoid memorizing CLI commands and fragile flags
- explicit enough for an operator to inspect processes, logs, memory pressure, profiles, and diagnostics
- structured enough to make good configurations repeatable

By default, LCC remains local to the Linux host and can be opened there at `http://127.0.0.1:17600`. Remote users can keep that safe default and reach it through SSH port forwarding. Direct access from a trusted local network is also supported, but requires an explicit bind address, authentication, and appropriate host security.

## Screenshots

![Lemonade Control Center dashboard](screenshot/lemonadecc_001.jpg)

| Setup Wizard | System |
|---|---|
| ![Setup wizard](screenshot/lemonadecc_005.jpg) | ![System monitoring](screenshot/lemonadecc_002.jpg) |

| Diagnostics | Hardware Monitor |
|---|---|
| ![Diagnostics](screenshot/lemonadecc_003.jpg) | ![Hardware monitor](screenshot/lemonadecc_004.jpg) |

## What's New In 0.3.0

Version 0.3.0 adds the first complete evidence-and-workflow layer on top of LCC's operator foundation:

- **Guided Hugging Face Intake** accepts a repository or simple model search, shows relevant GGUF variants and memory estimates, creates an optional workflow profile, and asks Lemonade to perform the pull.
- **Smoke Test and Run Evidence** verify the active model with a real completion and retain inspectable timing, token, runtime, profile, process, memory, and correlated-log evidence. Metric provenance is shown when a value is measured, reported, or estimated.
- **More useful Logs & Stats** expose TTFT, prompt and generation throughput, token counts, duration, finish reason, recent tasks, and parsed operational events.
- **Workflow Profiles and Workflow Memory** make successful model/runtime configurations repeatable and traceable into later smoke tests and comparisons.
- **Bench Lab** can compare the same coding-agent workflow across model/profile combinations and export the results. It is a working early-stage prototype whose suites, analysis, and presentation will continue to evolve.
- **Backend and deployment operations** add telemetry-provider visibility, guarded backend install/update actions, and container packaging for local or remote Lemonade targets.

See the [0.3.0 release notes](https://github.com/peppeg/Lemonade_Control_Center/releases/tag/0.3.0) and [Changelog](CHANGELOG.md) for the complete list. Hugging Face pulls currently notify when the download finishes; persistent progress and reconnectable download state are planned follow-up work.

## What You Can Do

### Use guided Lemonade workflows

LCC turns routine Lemonade operations into visible, guarded workflows. It can show the selected server, active model, downloaded inventory, load options, saved profiles, process state, and diagnostics in one place before the user changes runtime behavior.

This does create intentional overlap with official Lemonade tooling. The differentiation is not that LCC owns the server better than Lemonade. The differentiation is that LCC organizes common operations, host state, and operator context into one graphical workflow.

### See the runtime at a glance

The Dashboard brings together Lemonade health, the active model, recent inference metrics, hardware pressure, and warnings. It answers the basic questions before you start changing anything: what is running, how is the machine behaving, and does something need attention?

### Manage models

The Models workspace provides:

- local model inventory
- access to the remote Lemonade catalog
- model download, load, and unload controls
- active model and process details
- saved Lemonade options
- per-model LCC profiles
- guarded controls for common load options
- an advanced argument field with validation for experienced users

LCC distinguishes between model names exposed through compatibility APIs and the canonical names expected by Lemonade, so routine operations do not depend on users knowing those implementation details.

### Build repeatable configurations

The Configuration workspace separates two different kinds of state:

- **Runtime configuration**, owned by Lemonade and applied when models are loaded.
- **LCC workflow defaults**, stored locally and used by LCC-owned requests such as smoke tests and Bench Lab quick tests.

Workflow defaults do not reconfigure external clients such as Open WebUI or coding agents. Those clients continue to send their own request parameters.

Built-in profiles provide practical starting points such as Safe, Coding, Long Context, Stress, and Executor Strict. Risky settings remain explicit, and Lemonade-managed arguments are not silently duplicated.

### Compare workflows in Bench Lab

Bench Lab can run coding-agent-oriented suites against different model/profile combinations, retain prompts, outputs, reasoning, runtime and resource evidence, add operator quality scores, and export comparison reports.

Bench Lab is functional but still an early-stage surface. Its evidence foundation and comparison workflow work today, while its presentation, suite library, analysis tools, and overall shape are expected to evolve substantially. Test feedback is especially useful here; it should not yet be read as a finished benchmarking product or as a replacement for `lemonade bench`.

### Read logs as operational information

Logs & Stats turns server output into useful signals:

- input and output tokens
- time to first token
- prompt-processing and generation throughput
- total task duration
- finish reason
- parsed Lemonade logs and warnings
- recent task history

### Monitor the host

LCC monitors the Linux machine that actually runs the models:

- system RAM and swap
- CPU load
- AMD GPU load and temperature when exposed through Linux `sysfs`
- other available thermal sensors through `psutil` or `lm-sensors`
- root-disk usage
- `llama-server` PID, memory use, CPU use, uptime, and command line
- processes with the highest RAM consumption
- `lemond.service` and journal state when systemd is available

On unified-memory systems such as AMD Strix Halo, system RAM is the primary capacity signal. LCC does not currently present a separate VRAM-usage figure.

### Diagnose problems

Diagnostics combines runtime, service, hardware, and configuration checks into one report. It includes warning classification, dismissible findings, diagnostic history, and a downloadable support bundle.

Run Evidence keeps inspectable records for smoke tests and model-load attempts, including request/result metrics, runtime and profile identity, observed process and memory state, and correlated Lemonade logs when available. Individual records can be filtered, inspected, and exported as JSON or Markdown.

### Verify the active model with a smoke test

Smoke Test sends a small real completion through the active Lemonade runtime, displays the response and key latency/throughput values, and saves the result as Run Evidence. When a workflow profile is applied, that identity follows the test so the result records not just what ran, but the configuration intent behind it.

### Inspect and pull Hugging Face models

Guided Hugging Face Intake can inspect a repository or a simple search term, present relevant GGUF variants and memory estimates, create a workflow profile, and hand an explicit pull to Lemonade. Lemonade remains responsible for downloading, registering, importing, and updating the model.

### Configure the connection

Settings manages the Lemonade runtime URL, discovery checks, optional admin API key, local preferences, and project information. Secrets are stored by the backend and redacted from Settings responses.

## Product Direction

LCC is guided by three product pillars:

- **Guided GUI**: make Lemonade operations visible and safer without forcing users to remember CLI commands, ports, endpoints, and backend flags.
- **Operator Evidence**: correlate Lemonade state with Linux host state, service logs, process data, memory pressure, and hardware signals when available.
- **Workflow Memory**: keep profiles, saved options, benchmark results, notes, and diagnostics tied to the workflows they support.

The initial operator foundation and the first evidence/workflow delivery sequence are complete: Connection Doctor and guided loading, Run Evidence, workflow profiles, Bench Lab comparisons, telemetry providers, guided Hugging Face intake, and container packaging are all available on `main`. The next product phase focuses on multi-host operation and agent-readiness checks, while compatibility work and download-progress improvements continue in the maintenance lane.

See [Overlap Matrix](docs/overlap-matrix.md) and the [Roadmap Current Execution Plan](docs/roadmap.md#current-execution-plan) for product boundaries, current delivery state, implementation references, and the ordered remaining work.

## Safety Model

LCC is intentionally conservative about privileged and destructive operations.

- The backend binds to `127.0.0.1` by default.
- Model deletion is disabled unless `ENABLE_DELETE=true` is set explicitly.
- Service restart is disabled unless `ENABLE_RESTART=true` is set explicitly.
- Protected Lemonade operations require the Lemonade admin API key.
- Sensitive runtime configuration is excluded from the public repository.
- Destructive actions require confirmation.
- The UI adapts to capabilities detected on the actual machine.

Local inference workloads can consume tens of gigabytes of memory and can make a workstation temporarily unresponsive when configured badly. An operator console for that environment should explain consequences rather than turn every command into an inviting button.

## Architecture

LCC uses two services during development and one service for the real local runtime:

- a **FastAPI backend** for Lemonade integration, host inspection, metrics, profiles, diagnostics, and static frontend serving
- a **SvelteKit frontend** for the browser interface and operator workflows

```text
Browser
   │
   ▼
FastAPI
   ├── /api/*
   ├── /ws/*
   └── built SvelteKit frontend
   ├── Lemonade HTTP API
   ├── systemd / journal
   ├── Linux processes and sysfs
   └── local LCC configuration
```

Development keeps Vite and FastAPI separate for faster iteration. The unified runtime serves the built frontend and the API from the same FastAPI process.

### Backend responsibilities

- Lemonade API integration
- model and catalog operations
- runtime discovery
- profile storage
- hardware and process inspection
- log parsing and metrics collection
- diagnostics and support bundles
- local Run Evidence lookup, operation-window log correlation, and JSON/Markdown report generation
- shared OpenAI-compatible completion streaming for Smoke Test and optional Bench Lab workflows

### Frontend responsibilities

- application navigation
- runtime and hardware status
- model-management workflows
- configuration and profile editing
- logs, diagnostics, and settings
- Run Evidence filtering, detail inspection, and report download
- confirmations, warnings, and live feedback

## Requirements

- Linux
- Python 3.11 or newer
- Node.js 20 or newer
- a running Lemonade server

Host inspection works best when standard Linux facilities are available, including `systemctl`, `journalctl`, `/proc`, `/sys`, and hardware sensor support.

## Compatibility

LCC is currently tested against Lemonade Server `10.5.1`, `10.7.0`, and `10.9.0` on the primary development workstation. Lemonade `10.9.0` is the current active test target with caveats noted in the tested-environment document.

Lemonade can change model metadata and server configuration behavior between releases. LCC normalizes the API responses it uses, but new Lemonade versions should still be smoke-tested before relying on them for regular operation.

See [Tested Environment](docs/tested-environment.md) for the current hardware and software baseline.

## Runtime Setup

After cloning the repository, run the installer:

```bash
./install.sh
```

It creates the backend virtual environment, installs backend and frontend dependencies, builds the static frontend, and creates `backend/.env` from `.env.example` when missing.

Start the unified runtime:

```bash
cd backend
source .venv/bin/activate
python -m app.run
```

Open:

```text
http://127.0.0.1:17600
```

FastAPI serves both `/api/*` and the built dashboard. Vite is not needed for this mode.

### Container deployment

The repository includes a multi-stage LCC image and Compose examples for an API-only deployment or an explicit Linux host-telemetry override. The default container does not claim access to host processes, sysfs, accelerators, systemd, or journals.

The image has been built and runtime-tested with Podman on the primary development host. Native Docker and Docker Compose testers are welcome: the deployment is ready for testing, but has not yet been exercised with the Docker Compose plugin on that host.

See [Container Deployment](docs/deployment.md) for authentication, Lemonade networking, persistence, device mapping, and telemetry limitations.

### Access from another computer with SSH

When LCC remains bound to its safe localhost default, forward the application port from the client computer:

```bash
ssh -N -L 17600:127.0.0.1:17600 USER@SERVER_IP
```

Run this command from Windows PowerShell, Windows Terminal, or another computer with an OpenSSH client. Keep the SSH session open, then browse to:

```text
http://127.0.0.1:17600
```

Replace `USER` and `SERVER_IP` with the Linux account and address of the machine running LCC. The server remains bound to localhost and does not need to expose port `17600` directly to the network.

Manual setup is also possible.

Build the frontend once:

```bash
cd frontend
npm install
npm run build
```

Start the unified runtime:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python -m app.run
```

## Development Setup

Clone the repository and start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

During development, Vite proxies `/api` requests to FastAPI at `127.0.0.1:8000`.

## Configuration

The backend reads environment variables and `backend/.env`.

```env
LEMONADE_URL=http://localhost:13305
LEMONADE_ADMIN_API_KEY=
ENABLE_DELETE=false
ENABLE_RESTART=false
LCC_API_KEY=
REQUIRE_AUTH=false
APP_HOST=127.0.0.1
APP_PORT=17600
SERVE_FRONTEND=true
FRONTEND_BUILD_DIR=../frontend/build
LAN_MODE=false
```

| Variable | Description |
|---|---|
| `LEMONADE_URL` | URL of the Lemonade server |
| `LEMONADE_ADMIN_API_KEY` | Optional key for protected Lemonade operations |
| `ENABLE_DELETE` | Enables guarded model deletion when set to `true` |
| `ENABLE_RESTART` | Enables guarded service restart when set to `true` |
| `LCC_API_KEY` | Protects LAN and remote access to LCC |
| `REQUIRE_AUTH` | Requires `LCC_API_KEY` for every client, including localhost, when set to `true` |
| `APP_HOST` | Bind host for the unified runtime |
| `APP_PORT` | Bind port for the unified runtime |
| `SERVE_FRONTEND` | Serves the built frontend from FastAPI when `true` |
| `FRONTEND_BUILD_DIR` | Path to the SvelteKit static build |
| `LAN_MODE` | Requires explicit LAN bind and `REQUIRE_AUTH=true` when enabled |

### LAN access

For a trusted local network, LAN mode is an alternative to the SSH tunnel. It makes LCC directly reachable from another computer, so the SSH session does not need to remain open.

Set a long random `LCC_API_KEY` in `backend/.env`, then start LCC on a LAN-visible address:

```bash
APP_HOST=0.0.0.0 APP_PORT=4242 REQUIRE_AUTH=true LAN_MODE=true python -m app.run
```

From Windows or another computer on the same network, open:

```text
http://SERVER_IP:4242
```

Replace `SERVER_IP` with the private LAN address of the Linux host. Enter the configured `LCC_API_KEY` when prompted. The host firewall must allow TCP port `4242`.

SSH tunnel mode and LAN mode are alternatives: use the tunnel for the safest default, or LAN mode for direct access on a trusted private network. Do not expose LCC directly to the public internet.

### Lemonade admin API key

Most LCC features do not require an admin key. Lemonade uses it to protect internal administrative endpoints.

When Lemonade runs as a systemd service, configure the key through a service override:

```bash
sudo systemctl edit lemond.service
```

```ini
[Service]
Environment=LEMONADE_ADMIN_API_KEY=your-generated-secret
```

Then reload systemd and restart Lemonade:

```bash
sudo systemctl daemon-reload
sudo systemctl restart lemond.service
```

> Restarting `lemond.service` unloads the active model.

Save the same key in LCC from **Settings → Connection**.

## Capability Probe

The optional probe utility captures the Lemonade endpoints and host facilities available on a particular installation:

```bash
cd capabilities
pip install -r requirements.txt
python probe.py
```

When an admin key is configured:

```bash
python probe.py --admin-key YOUR_ADMIN_KEY
```

Structured results are written under `capabilities/results/`. These files are local machine artifacts and are ignored by git.

For a generic example, see [capabilities/CAPABILITIES.example.md](capabilities/CAPABILITIES.example.md).

## Documentation

- [Installation](docs/installation.md)
- [Development](docs/development.md)
- [Security Model](docs/security.md)
- [Tested Environment](docs/tested-environment.md)
- [Overlap Matrix](docs/overlap-matrix.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Repository Layout

```text
.
├── backend/          FastAPI backend
│   └── app/
│       ├── models/
│       ├── providers/
│       ├── routers/
│       └── services/
├── frontend/         SvelteKit frontend
│   └── src/
├── docs/             Public project documentation
├── capabilities/     Capability probe tooling and sanitized example
├── .env.example      Example backend configuration
└── LICENSE
```

## Project Status

Lemonade Control Center is under active development. The core application surfaces are operational, but behavior can vary with the installed Lemonade version, available Linux facilities, enabled safety flags, and local hardware.

Container deployment, guided model intake, workflow profiles, Run Evidence, telemetry providers, and Bench Lab workflow comparisons are available for testing. Some newer surfaces—especially Bench Lab—are intentionally still evolving and do not yet represent their final product shape.

Feedback and carefully scoped contributions are welcome.

## Credits

Created by [Peppe / peppeg](https://github.com/peppeg), creator of [yourfuture.me](https://yourfuture.me).

Project repository: [peppeg/Lemonade_Control_Center](https://github.com/peppeg/Lemonade_Control_Center)

Built with FastAPI, SvelteKit, Tailwind CSS, Lucide, and the Lemonade ecosystem.

Development assistance included OpenAI Codex, Qwen3-Coder-Next-GGUF, and Google Stitch for UI exploration.

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
