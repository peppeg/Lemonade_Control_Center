# Changelog

All notable public changes to Lemonade Control Center will be documented here.

The project is under active development, so entries currently describe the evolving application surface rather than stable releases.

## Unreleased

No unreleased changes yet.

## 0.2.0 - 2026-07-09

### Added

- Public operator-console positioning and roadmap documentation.
- Overlap matrix separating Lemonade CLI, official Web UI/App, and API surfaces.
- Public compatibility discipline documented through roadmap and tested-environment notes.
- Lemonade `10.9.0` tested-environment notes.
- Lemonade server discovery through UDP beacon listening and HTTP fallback probes in setup.
- Connection Doctor V0 in Settings for Lemonade runtimes, including health, version, local/remote target classification, host telemetry applicability, process evidence, admin config status, warnings, and recommended next action.
- Guided Load V2 preflight in the model load dialog with model size, planning headroom, safe context estimate, context risk, active process impact, and saved Lemonade defaults.
- Post-load notification details for observed backend, context, and PID when process evidence is available.

### Changed

- Clarified that LCC is an unofficial guided operator console for Lemonade, not a replacement for the official Web UI, not a chat client, and not a model marketplace.
- Updated README compatibility guidance for Lemonade `10.9.0`.
- Strengthened Lemonade-managed `llamacpp_args` validation for newer draft/speculative-model flags.
- Updated the P0 roadmap to track Connection Doctor V0 and Guided Load V2 progress.

### Fixed

- Preserved runtime admin key state when updating runtime settings without entering a new key.
- Normalized pasted Lemonade URLs ending in `/api/v1` or `/v1`.

## 0.1.0 - 2026-06-19

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
