# Tested Environment

Lemonade Control Center is designed for Linux inference hosts. The current development and manual testing environment is listed here so users can understand the hardware and software baseline behind the project.

This is not a minimum requirement.

## Primary Development Machine

| Item | Value |
|---|---|
| Workstation | Corsair AI Workstation 300 |
| Operating system | Fedora Linux 44 Workstation |
| Kernel | 7.0.9-202.fc44.x86_64 |
| Processor | AMD Ryzen AI Max+ 395 with Radeon 8060S |
| Memory | 128 GB unified memory |
| Lemonade Server | 10.7.0 |
| Runtime backend used most often | Lemonade llama.cpp backend |
| Main development workflow | LCC unified FastAPI runtime on localhost, browser from local machine or SSH tunnel |

## Lemonade Compatibility

| Lemonade Server | Status | Notes |
|---|---|---|
| 10.5.1 | tested | Original development baseline |
| 10.6.x | not yet tested | No public compatibility claim yet |
| 10.7.0 | tested | Previous active test target |
| 10.8.x | not yet tested | Release notes reviewed; requires smoke testing before compatibility claim |
| 10.9.0 | tested with caveats | Current active test target; probe, backend tests, frontend check/build, and basic LCC runtime smoke passed |

Manual smoke tests on Lemonade `10.7.0` passed for:

- Dashboard runtime health and version display
- Models downloaded inventory
- Models remote catalog refresh
- Settings active runtime test
- Settings runtime discovery

Observed `10.7.0` API notes:

- `/api/v1/models` uses `components` where the older probe output used `composite_models`
- `/api/v1/models` still exposes model `size` as a float in GiB
- `/api/tags` still exposes model `size` as integer bytes

Lemonade `10.9.0` upgrade checks passed on 2026-07-09 for:

- Lemonade health and version display
- LCC capability probe
- Backend unit tests
- Frontend type check
- Frontend production build
- Unified LCC runtime health endpoint
- LCC Lemonade health proxy
- LCC downloaded model inventory via `/api/lemonade/models`

Observed `10.9.0` API notes:

- `/api/v1/health` adds `pinned_models`, `telemetry`, and `update_check_done`.
- `/api/v1/health` still exposes `all_models_loaded`, `model_loaded`, `max_models`, `status`, `version`, and `websocket_port`.
- Startup logs report Hugging Face model update availability when detected.
- Full load/unload and Bench Lab smoke tests are still pending after the upgrade.

## Notes

- AMD Strix Halo is the main target hardware during development.
- LCC should run on other Linux hosts, but hardware monitoring depends on what the host exposes through `/proc`, `/sys`, `psutil`, systemd, journal logs, and sensor tooling.
- GPU load and temperature support is currently focused on AMD Linux `sysfs` data.
- Public documentation avoids committing raw probe output because it may include model names, process command lines, local paths, service logs, and host-specific details.
