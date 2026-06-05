# Lemonade Control Center

**Lemonade Control Center** is an unofficial local control panel for [Lemonade](https://github.com/lemonade-sdk/lemonade), built for people who run large language models on their own machine and want a clearer way to operate the runtime.

It is not a chat interface. It is an operator console for the server behind the chat interface.

The goal is to replace repeated terminal commands, shell one-liners, manual log checks, and scattered runtime notes with a focused web dashboard for model loading, runtime visibility, hardware monitoring, diagnostics, and guarded configuration.

## Screenshots

Screenshots will be added as the interface stabilizes.

## What It Does

Lemonade Control Center is designed to sit next to tools such as Open WebUI or other chat frontends.

- **Chat UI**: talk to the model.
- **Lemonade Control Center**: understand, configure, monitor, and operate the local inference runtime.

The application focuses on the operational layer:

- Is Lemonade reachable?
- Which model is loaded?
- Which models are installed locally?
- Which models are available from the Lemonade catalog?
- How much RAM, GPU, and system headroom is available?
- What was the last task?
- Which logs and warnings matter?
- Which runtime options are safe to expose?
- Which actions require explicit confirmation or an admin key?

## Main Surfaces

### Dashboard

The dashboard gives a compact overview of the local runtime:

- Lemonade connection state
- active model
- recent task metrics
- RAM and GPU usage
- runtime health
- important warnings

### Models

The Models page is the main place to manage local and downloadable models:

- local model inventory
- remote Lemonade catalog refresh
- model load and unload
- active model details
- per-model profile awareness
- safer controls for common load options
- guarded extra arguments for advanced users

The intent is not to hide technical detail. Local inference is technical, and some options can have serious memory or stability implications. Lemonade Control Center keeps those options visible, but organizes them so users can understand what they are about to do.

### Configuration

The Configuration page focuses on runtime and request defaults:

- profile-oriented settings
- context size and slot planning
- request defaults
- safe Lemonade / llama.cpp argument handling
- warnings for risky or unsupported combinations

The application avoids guessing when an option is runtime-owned by Lemonade. Where Lemonade already manages a flag internally, Lemonade Control Center should expose the state clearly rather than encouraging duplicate manual arguments.

### Logs and Stats

The Logs and Stats page turns runtime noise into readable operational signals:

- parsed recent logs
- last task information
- input and output token metrics where available
- runtime warnings
- task history
- live backend-derived updates

### Hardware

The Hardware page is built for local AI workstations where memory pressure and GPU load matter:

- system RAM usage
- swap visibility
- GPU load
- GPU temperature where available
- CPU load where useful
- host-level sensor support on Linux

### System

The System page focuses on the host process and service layer:

- Lemonade service status
- detected `llama-server` process
- process command line visibility
- systemd and journal integration when available
- guarded restart actions

### Diagnostics

The Diagnostics page provides structured checks and support data:

- runtime discovery checks
- hardware and service probes
- warning and error classification
- diagnostic history
- downloadable diagnostic bundle

This is meant to make troubleshooting easier without requiring every user to know which command to run first.

### Settings

The Settings page manages local application configuration:

- configured runtimes
- active Lemonade connection
- runtime discovery
- optional Lemonade admin API key
- local preferences
- project and system information

## Safety Model

Lemonade Control Center is intentionally conservative.

- The backend binds to localhost by default.
- Destructive actions are disabled unless explicitly enabled.
- Service restart is disabled unless explicitly enabled.
- Lemonade admin operations require the Lemonade admin API key.
- Sensitive local configuration is stored outside the public repository.
- The UI is capability-driven and should not show unsafe actions as normal controls.

This matters because the application is expected to operate local models that can consume tens of gigabytes of RAM and GPU memory. A control panel for that environment should be explicit, not casual.

## Lemonade Admin API Key

Some Lemonade operations are intentionally protected by an admin API key.

If Lemonade is running as a systemd service, the key should be configured on the Lemonade service itself, for example through a systemd override:

```bash
sudo systemctl edit lemond.service
```

```ini
[Service]
Environment=LEMONADE_ADMIN_API_KEY=your-generated-secret
```

Then reload and restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart lemond.service
```

The same key can then be saved in Lemonade Control Center from the Settings page.

Restarting `lemond.service` unloads the currently loaded model.

## Architecture

The project is split into two layers during development.

### Backend

The backend is a FastAPI service responsible for:

- Lemonade API integration
- runtime discovery
- model and catalog operations
- profile storage
- hardware inspection
- process and service inspection
- log parsing
- metrics collection
- diagnostic bundle generation

Main local API groups include:

- `/api/health`
- `/api/lemonade/*`
- `/api/system/*`
- `/api/logs/*`
- `/api/metrics/*`
- `/api/profiles/*`
- `/api/diagnostics/*`
- `/api/settings/*`
- `/api/setup/*`

### Frontend

The frontend is a SvelteKit application responsible for:

- application shell
- dashboard and navigation
- operator workflows
- model management UI
- configuration forms
- settings and discovery views
- live feedback

The development setup uses Vite for the frontend and FastAPI for the backend. The intended packaged experience is a single local application service that can serve both the API and the built dashboard.

## Repository Layout

```text
.
├── backend/          FastAPI backend
│   ├── app/
│   │   ├── routers/  API route groups
│   │   ├── providers/
│   │   ├── services/
│   │   └── models/
│   └── requirements.txt
├── frontend/         SvelteKit frontend
│   ├── src/
│   └── package.json
├── capabilities/     Probe tooling and captured capability results
├── .env.example      Example local configuration
└── LICENSE
```

## Requirements

- Linux
- Python 3.11+
- Node.js 20+
- a running Lemonade server

Host-level inspection works best on Linux systems with standard tools such as:

- `systemctl`
- `journalctl`
- `/proc`
- `psutil`
- system sensor files where available

## Development Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Default backend URL:

```text
http://127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Default frontend URL:

```text
http://127.0.0.1:5173
```

During development, the frontend proxies `/api` requests to the local FastAPI backend.

## Configuration

The backend reads configuration from environment variables or from `backend/.env`.

Example:

```env
LEMONADE_URL=http://localhost:13305
LEMONADE_ADMIN_API_KEY=
ENABLE_DELETE=false
ENABLE_RESTART=false
```

Key options:

- `LEMONADE_URL`: Lemonade server URL.
- `LEMONADE_ADMIN_API_KEY`: optional key for protected Lemonade admin operations.
- `ENABLE_DELETE`: enables guarded model deletion when set to `true`.
- `ENABLE_RESTART`: enables guarded service restart when set to `true`.

## Capability Probe

The `capabilities/` directory contains a probe utility for capturing Lemonade and host capabilities.

```bash
cd capabilities
pip install -r requirements.txt
python probe.py
```

With an admin key:

```bash
python probe.py --admin-key YOUR_ADMIN_KEY
```

The probe writes structured results under `capabilities/results/` and generates a capability summary.

## Project Status

Lemonade Control Center is under active development.

The repository already contains the main backend and frontend structure, with working local surfaces for runtime status, model management, configuration, logs, hardware, diagnostics, and settings. Some features depend on the installed Lemonade version, available host tools, enabled safety flags, and whether the Lemonade admin API key is configured.

## Credits

Created by Peppe / [peppeg](https://github.com/peppeg).

Project repository: [peppeg/Lemonade_Control_Center](https://github.com/peppeg/Lemonade_Control_Center)

Personal site: [yourfuture.me](https://yourfuture.me)

Built with FastAPI, SvelteKit, Tailwind CSS, Lucide, and the Lemonade local LLM ecosystem.

Development assistance included OpenAI Codex, Qwen3-Coder-Next-GGUF, and Google Stitch for UI exploration.

## License

Licensed under the Apache License, Version 2.0.

See [LICENSE](LICENSE).
