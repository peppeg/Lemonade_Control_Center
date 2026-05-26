# Lemonade Control Center

Unofficial web admin console for Lemonade local LLM servers.

Lemonade Control Center is a capability-driven control plane for running and managing Lemonade-based local LLM servers. The goal is straightforward: replace ad hoc workflows built around `curl`, `journalctl`, `ps`, and shell one-liners with a focused web UI that exposes the operational side of a local inference stack.

This project is not a chat UI. It is an operator console.

## What It Is

Lemonade Control Center is designed for people who run local models seriously and need visibility into:

- server health
- loaded models
- runtime configuration
- last-task performance
- logs and warnings
- hardware state
- service status
- diagnostics and support bundles

The intended split is:

- **Open WebUI**: interact with models
- **Bench Lab**: test and compare models
- **Lemonade Control Center**: administer the runtime

## Project Goals

The long-term target is a practical admin console for Lemonade with:

- a fast local web UI
- a Python backend that can talk both to Lemonade and to the host system
- capability-driven behavior, so the UI adapts to the real server and machine
- safety gates around destructive actions
- diagnostics that are readable by humans, not only by shell users

## Core Design Principles

### 1. Capability-Driven UI

The app does not assume that every Lemonade endpoint exists or behaves exactly as documented.

At startup, and after the probe step, the backend exposes a capabilities model to the frontend. The frontend uses it to decide:

- which actions are available
- which buttons must be disabled
- which features can be shown safely
- which platform-specific system integrations exist

That matters because local Lemonade installs can differ by:

- version
- enabled internal endpoints
- available host commands
- admin key configuration
- deployment style

### 2. Safe by Default

Destructive or host-level actions are gated.

Current model:

- model deletion is disabled by default
- service restart is disabled by default
- internal Lemonade config endpoints require an admin key
- the backend binds to localhost by default

The project is explicitly biased toward read-only visibility first, then guarded operations.

### 3. Split Responsibilities

The backend owns:

- Lemonade API integration
- capability probing
- system inspection
- process parsing
- log parsing
- diagnostic bundle generation

The frontend owns:

- operator workflow
- status surfaces
- navigation
- feature gating presentation
- live feedback and placeholders for milestone work

## Architecture

### Backend

Stack:

- FastAPI
- Pydantic / pydantic-settings
- HTTPX
- host command integration where needed

Responsibilities:

- proxy Lemonade endpoints through a stable local API
- expose health and capabilities
- inspect hardware and processes
- parse recent logs and task stats
- generate downloadable diagnostic bundles

Main API groups:

- `/api/health`
- `/api/capabilities`
- `/api/lemonade/*`
- `/api/system/*`
- `/api/logs/*`
- `/api/diagnostic-bundle`

### Frontend

Stack:

- SvelteKit
- Tailwind CSS
- Lucide icons

Responsibilities:

- shell layout
- status presentation
- milestone pages
- capability-driven navigation and controls

## Planned Feature Surface

The intended final product includes the following operator surfaces.

### Dashboard

- backend health
- Lemonade reachability
- version and ports
- loaded model summary
- service status
- smart warnings

### Models

- installed models
- running models
- load / unload
- delete when explicitly enabled
- model details
- runtime parameter visibility

### Configuration

- current Lemonade config
- guarded config updates
- runtime defaults vs request defaults
- future presets and profile flows

### Logs and Stats

- recent parsed logs
- last-task metrics
- inferred warnings such as truncation
- live log streaming

### System

- RAM / CPU / disk
- temperatures when available
- `llama-server` process discovery
- `lemond.service` status
- guarded restart

### Diagnostics

- one-click ZIP diagnostic bundle
- metadata, logs, health, models, hardware, service state

## Current Status

This repository is under active development.

Broadly:

- **M0**: capabilities probe exists
- **M1**: project scaffolding exists
- **M2**: backend core exists
- **M3**: frontend shell exists in-progress and is currently being repaired

If you are reading this during development, assume that:

- backend endpoints are the most trustworthy part of the codebase
- frontend shell and UI layer are still being normalized
- roadmap and implementation-plan documents are the source of truth for milestone scope

Relevant planning documents in this repo:

- `lemonade_control_center_overview.md`
- `implementation_plan.md`
- `implementation_plan_M0.md`
- `implementation_plan_M1.md`
- `implementation_plan_M2.md`
- `implementation_plan_M3.md`

## Repository Layout

```text
.
├── backend/                 FastAPI backend
│   ├── app/
│   │   ├── routers/         API route groups
│   │   ├── providers/       Lemonade integration layer
│   │   ├── services/        hardware, process, log parsing
│   │   └── models/          Pydantic schemas
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/                SvelteKit frontend
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   ├── components/
│   │   │   ├── stores/
│   │   │   ├── types/
│   │   │   └── utils/
│   │   └── routes/
│   └── package.json
├── capabilities/            Probe script and captured results
├── implementation_plan*.md  Roadmap and milestone planning
└── lemonade_control_center_overview.md
```

## Requirements

### Runtime Requirements

- Python 3.11+
- Node.js 20+
- a running Lemonade server
- Linux environment if you want host inspection features such as `journalctl`, `systemctl`, and `sensors`

### Recommended Environment

The project is intended first for local Linux machines running Lemonade directly or as a service. Fedora, Ubuntu, and similar setups are the natural target.

## Configuration

The backend reads configuration from environment variables or a local `.env` file.

Example:

```env
LEMONADE_URL=http://localhost:13305
LEMONADE_ADMIN_API_KEY=
ENABLE_DELETE=false
ENABLE_RESTART=false
```

Notes:

- `LEMONADE_ADMIN_API_KEY` is required for internal Lemonade config endpoints
- `ENABLE_DELETE=false` keeps model deletion disabled
- `ENABLE_RESTART=false` keeps service restart disabled

See [.env.example](.env.example).

## Development Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```

Default backend URL:

- `http://127.0.0.1:8000`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Default frontend URL:

- `http://localhost:5173`

The frontend is configured to proxy `/api` requests to the local FastAPI backend during development.

## Capability Probe

Before relying on capability-driven behavior, run the probe against the target Lemonade install.

```bash
cd capabilities
pip install -r requirements.txt
python probe.py
```

With an admin key:

```bash
python probe.py --admin-key YOUR_ADMIN_KEY
```

The probe generates:

- `capabilities/results/*.json`
- `capabilities/results/probe_summary.json`
- `capabilities/CAPABILITIES.md`

Re-run it when:

- Lemonade is updated
- the admin key changes
- the host machine changes
- the server configuration changes materially

## API Surface

The backend currently organizes its public local API like this.

### Health and Capabilities

- `GET /api/health`
- `GET /api/capabilities`

### Lemonade Proxy Layer

- `GET /api/lemonade/health`
- `GET /api/lemonade/stats`
- `GET /api/lemonade/system-info`
- `GET /api/lemonade/models`
- `GET /api/lemonade/running`
- `GET /api/lemonade/models/{model_name}`
- `POST /api/lemonade/load`
- `POST /api/lemonade/unload`
- `DELETE /api/lemonade/models/{model_name}`
- `GET /api/lemonade/config`
- `POST /api/lemonade/config`

### System

- `GET /api/system/hardware`
- `GET /api/system/temperatures`
- `GET /api/system/processes`
- `GET /api/system/llama-server`
- `GET /api/system/service`
- `POST /api/system/restart`

### Logs

- `GET /api/logs/recent`
- `GET /api/logs/last-task`
- `WS /api/logs/ws/logs`

### Diagnostic Bundle

- `GET /api/diagnostic-bundle`

## Safety Model

The project intentionally separates:

- runtime-level operations
- request-default tuning
- destructive actions

Current safety posture:

- no delete without explicit opt-in
- no restart without explicit opt-in
- no internal config write without admin key
- capability checks happen before the frontend offers operations

This matters because an admin console should not guess.

## Near-Term Roadmap

The current execution path is centered on stabilizing the frontend shell and then layering real operator views on top of the backend that already exists.

Near-term priorities:

1. repair and normalize the M3 frontend shell
2. wire dashboard surfaces to real backend data
3. expose model management flows
4. expose guarded configuration editing
5. expose parsed logs, stats, and diagnostics cleanly

## Runtime Direction

Development and final runtime are intentionally not the same thing.

- **Development** uses two processes:
  - SvelteKit/Vite for the frontend
  - FastAPI for the backend
- **Final runtime** is planned as a single local service:
  - FastAPI serves `/api/*`
  - FastAPI also serves the built frontend dashboard

The target user experience is one application, one port, one start command.

Planned default runtime shape:

- dev backend: `127.0.0.1:8000`
- dev frontend: `localhost:5173`
- final app runtime: `127.0.0.1:17600`

`8000` is treated as a development port, not the intended product-facing default.

## Contributing

This project is still early, so contribution quality matters more than contribution volume.

If you contribute:

- prefer small, reviewable changes
- keep behavior capability-driven
- avoid adding destructive actions without explicit gating
- keep frontend and backend contracts typed and explicit
- document assumptions when integrating Lemonade behavior that may vary by version

## License

Current repository license: **Apache-2.0**.

See [LICENSE](LICENSE).
