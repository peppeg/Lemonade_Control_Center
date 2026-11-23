# Tested Environment

Lemonade Control Center is designed for Linux inference hosts. The current development and manual testing environment is listed here so users can understand the hardware and software baseline behind the project.

This is not a minimum requirement.

## Primary Development Machine

| Item | Value |
|---|---|
| Workstation | Corsair AI Workstation 300 |
| Operating system | Fedora Linux 44 Workstation |
| Kernel | 7.2.15-200.fc44.x86_64 |
| Processor | AMD Ryzen AI Max+ 395 with Radeon 8060S |
| Memory | 128 GB unified memory |
| Lemonade Server | 2026.45.3 |
| Runtime backend used most often | Lemonade llama.cpp backend |
| Main development workflow | LCC unified FastAPI runtime on localhost, browser from local machine or SSH tunnel |

## Lemonade Compatibility

| Lemonade Server | Status | Notes |
|---|---|---|
| 10.5.1 | tested | Original development baseline |
| 10.6.x | not yet tested | No public compatibility claim yet |
| 10.7.0 | tested | Previous active test target |
| 10.8.x | not yet tested | Release notes reviewed; requires smoke testing before compatibility claim |
| 10.9.0 | tested with caveats | Full test pass for LCC 0.3.0; probe, backend tests, frontend check/build, and basic LCC runtime smoke passed |
| 11.x | not formally tested | Compatibility fixes for 11.7 telemetry, nested config keys, and saved model options are merged (see Changelog), without a full test pass. The next tested version is 2026.45.3 |
| 2026.45.3 | tested with caveats | Test pass for LCC 0.3.1 on 2026-11-23; see [below](#lcc-031-on-lemonade-2026453) |

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

Manual workflow validation completed on 2026-07-11 through 2026-07-13 for:

- model load/unload and profile-linked Smoke Test;
- Run Evidence filtering, identity, detail, and export workflows;
- Workflow Profile apply, Apply & Load, and evidence linkage;
- same-suite Bench Lab comparison with manual quality notes and Markdown export;
- telemetry-provider presentation and accelerator-ownership caveats;
- guided Hugging Face inspection, profile creation, pull, model discovery, load, and Smoke Test;
- backend update confirmation through LCC's `/v1/install` integration: `llamacpp:rocm` changed from `update_required` to `installed`;
- post-update model reload and Smoke Test on `llamacpp:vulkan` (`LCC_SMOKE_OK`, TTFT 0.549 s, 4.2 tok/s, context 16,384).

Observed `10.9.0` API notes:

- `/api/v1/health` adds `pinned_models`, `telemetry`, and `update_check_done`.
- `/api/v1/health` still exposes `all_models_loaded`, `model_loaded`, `max_models`, `status`, `version`, and `websocket_port`.
- Startup logs report Hugging Face model update availability when detected.
- The `llamacpp:rocm` package update path is validated, but inference with the updated ROCm backend is not claimed: the post-update model reload and Smoke Test used Vulkan.

## LCC 0.3.1 On Lemonade 2026.45.3

Tested on 2026-11-23 on the primary development machine, with the llama.cpp ROCm backend (`b11836`). The hardware tests ran on the release candidate; the only later code change is the log redaction ([#47](https://github.com/peppeg/Lemonade_Control_Center/pull/47)), which was checked in the container and was active during the SSH tunnel test.

Passed:

- Update of an existing data directory: content preserved, directory `0700`, `config.json` `0600`.
- Load and unload of three models (9B, 31B with MTP draft, and a 45 GB MoE with a 262,144-token context), with saved options applied and left unchanged. GTT usage was read correctly up to 51 GB, and memory was released on unload.
- Smoke Test, also with reasoning on. When reasoning used the whole token budget, the result said so.
- Task telemetry: model, completion time, token counts, and rates matched the journal.
- Live metrics and log streams under load, and a Bench Lab quick run.
- Through an SSH tunnel, in a browser on another machine: Smoke Test, live charts, and Logs & Stats. Every main page also loaded in a headless browser on the host without console errors or failed requests.
- Access rules on the running server: foreign `Host` and `Origin`, forwarded headers, and cross-site requests were all refused, on the API and on WebSockets.
- Container with Podman 5.8.9: build, start, clean stop, data volume permissions, the health check command, and a Smoke Test against Lemonade on the host. Behind a Caddy proxy, the API and WebSockets worked with the key and were refused without it.

Not tested: changing the Lemonade configuration, model download and deletion, backend installation, service restart, the NPU, access from the local network without a tunnel, and native Docker Compose. Loading several models was tested only against a stand-in server.

Problems found, all present in 0.3.0 too and still open in 0.3.1:

- The `llama-server` process is found by searching whole command lines, so another program that mentions it can be shown instead, with its command line.
- When Lemonade drops a `total time` log line, the task gets the duration of an earlier one. In this host's journal, 9 of 241 completions since October had no such line. [#38](https://github.com/peppeg/Lemonade_Control_Center/pull/38) avoids this in the stored history, not in the last-task view.
- After Clear, the latest task comes back from the journal.
- With several models loaded, the first one is taken as the active one, and Run Evidence can name the wrong model ([#36](https://github.com/peppeg/Lemonade_Control_Center/issues/36)).
- Dashboard and Diagnostics read the default backend from `llamacpp_backend`, which Lemonade now nests as `llamacpp.backend`.
- A client that closes `/api/logs/ws/logs` while the journal is silent leaves a `journalctl` process behind, and LCC then does not stop until the next log line. The LCC frontend does not use that stream.

Observed `2026.45.3` API notes:

- The version scheme changed from `11.x` to a date-based one.
- `/api/v1/health` lists every loaded model in `all_models_loaded`, with `type`, `pid`, `backend_url`, and `recipe_options`.
- `/internal/config` reports `config_version` 2, with backend settings in nested sections.
- The backend is started without `-ngl` and `--mmap` options, so LCC shows GPU offload and mmap as unknown.
- Log lines written by different threads can swap their `(Process)` and `(Telemetry)` tags.

## Notes

- AMD Strix Halo is the main target hardware during development.
- LCC should run on other Linux hosts, but hardware monitoring depends on what the host exposes through `/proc`, `/sys`, `psutil`, systemd, journal logs, and sensor tooling.
- GPU load and temperature support is currently focused on AMD Linux `sysfs` data.
- Public documentation avoids committing raw probe output because it may include model names, process command lines, local paths, service logs, and host-specific details.
