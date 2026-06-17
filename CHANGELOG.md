# Changelog

All notable public changes to Lemonade Control Center will be documented here.

The project is under active development, so entries currently describe the evolving application surface rather than stable releases.

## Unreleased

### Added

- FastAPI backend for Lemonade integration, host inspection, profiles, metrics, diagnostics, and settings.
- SvelteKit frontend with Dashboard, Models, Configuration, Logs & Stats, System, Diagnostics, Settings, Setup, Hardware Monitor, and gated Bench Lab surfaces.
- First-run setup wizard for runtime connection, host capabilities, discovery, and completion state.
- Model inventory, remote Lemonade catalog refresh, download controls, load/unload workflows, active model details, and per-model profiles.
- Runtime and request configuration workspaces with guarded Lemonade llama.cpp argument controls.
- Last-task metrics, parsed logs, recent task history, and WebSocket-backed metrics updates.
- Linux host monitoring for RAM, swap, CPU, disk, process state, AMD GPU load, GPU temperature, and available sensors.
- Diagnostics checks, notifications, diagnostic history, and downloadable support bundle.
- Minimal LAN access control with `LCC_API_KEY`, optional `REQUIRE_AUTH=true`, localhost trust by default, and audit logging for mutating API requests.
- Public README with screenshots, safety model, architecture, configuration, and development setup.

### Changed

- Refined the application shell and sidebar behavior to match the current operator-console UI direction.
- Clarified setup wizard runtime choices: Lemonade is the current configured runtime, while Ollama and direct llama.cpp support are reserved for future runtime work.

### Security

- Destructive model deletion requires `ENABLE_DELETE=true`.
- Service restart requires `ENABLE_RESTART=true`.
- Lemonade protected operations require `LEMONADE_ADMIN_API_KEY`.
- LAN and remote API access require `LCC_API_KEY`.
