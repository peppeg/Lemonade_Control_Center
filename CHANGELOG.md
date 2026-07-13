# Changelog

All notable public changes to Lemonade Control Center will be documented here.

The project is under active development, so entries currently describe the evolving application surface rather than stable releases.

## Unreleased

### Changed

- Settings and Setup now show the LCC host environment and telemetry scope detected by the backend instead of presenting an unused manual OS-type selector. Existing `os_type` configuration remains readable for backward compatibility.
- The Dashboard no longer repeats the normal no-model idle state as both a smart alert and a diagnostic preview; the status strip and Loaded Model card remain the two intentional status/action surfaces.

## 0.3.0 - 2026-07-13

### Added

- Confirmed backend install/update actions on the Backends page, using Lemonade's public `/v1/install` API with `force=false`, authoritative readiness revalidation, busy/error feedback, and no shell-command execution.
- Post-load smoke test action for the active model, using Lemonade's OpenAI-compatible chat endpoint.
- First Run Evidence seed records with prompt, response, TTFT, token speed, token counts, finish reason, RAM/swap snapshots, and observed process/backend/context details.
- Local rolling Run Evidence storage and API endpoints for smoke-test evidence retrieval.
- Sanitized diagnostic bundle generation with manifest, README, local target snapshot, and recent Run Evidence summary.
- Diagnostic bundle download action on the Diagnostics page.
- Load attempts now create Run Evidence records with requested options, observed process/backend/context, memory snapshots, duration, and mismatch warnings.
- Load dialog result panel showing requested versus observed backend/context, PID, RSS, RAM delta, duration, evidence id, and load warnings.
- P0 closeout documentation with official Lemonade docs audit notes and P1/P2 deferrals.
- Backend and update event surfacing in Logs & Stats for Lemonade backend installs, llama-server upgrades, and model update notices.
- Backend Readiness summary on the Dashboard plus a dedicated Backends page with state filters, backend versions, devices, and operator actions.
- Typed Backend Readiness API derived from Lemonade system-info, with defensive normalization and state counts.
- Backend readiness snapshots in diagnostic bundles, including an explicit unavailable state when Lemonade cannot be reached.
- LCC Workflow Defaults with automatic migration from the previous browser storage key.
- Core OpenAI-compatible CompletionRunner shared by Smoke Test and Bench Lab, with structured errors, active-runtime routing, reasoning separation, and defensive SSE parsing.
- Run Evidence workspace with result filters, full record inspection, and per-run JSON or Markdown export.
- Run Evidence detail and export API endpoints with backend-tested lookup, filtering, and attachment handling.
- Per-run Lemonade journal windows captured for smoke tests and load attempts, with structured timestamps, levels, messages, and explicit unavailable/error states.
- Run Evidence identity linkage for the active LCC runtime, normalized server URL, workflow profile, and requested versus observed model names.
- Workflow Memory metadata for profile intent, operator notes, known caveats, target runtime, and the latest successful Run Evidence reference.
- Coding-agent Bench Lab suite, runtime/profile/resource evidence, manual quality assessments, and same-suite comparison reports.
- Typed telemetry providers for Linux process/sysfs, optional `amdgpu_top`, and optional `xdna-top`, with per-metric provenance and quality.
- Guided Hugging Face repository intake with Lemonade-backed GGUF variants, ONNX relevance checks, memory estimates, and workflow-profile creation.
- Multi-stage non-root LCC container image, loopback-bound authenticated Compose deployment, opt-in Linux host-telemetry override, and persistent local-data volume.

### Changed

- The application header now shows only the current page name, the footer keeps operational identity concise, and primary card icons follow a consistent accent/status color rule.
- Backend rows keep the primary Install/Update action visible while CLI fallback, status message, release link, and filename remain available in collapsed technical details.
- Backend technical actions recognize embedded HTTP links, render them as links, and copy only the URL instead of surrounding instructional text.
- Dashboard hardware pressure no longer duplicates the Hardware card; model details route to the active model workspace instead of the generic System page.
- Model inventory actions align consistently, profile secondary actions use compact accessible icon buttons, and Apply & Load now uses a launch-oriented Rocket icon.
- Configuration presets adapt between a compact mobile selector and a single-line desktop control with a deliberately two-line description; llama-server command-line details are open by default.
- Run Evidence uses a narrower fixed-layout run list with split date/time cells and page-level scrolling instead of nested scrollbars.
- Settings About now distinguishes the LCC version from the configuration schema, links to the changelog, and removes obsolete M14 milestone language.
- Diagnostics now reads admin-key presence from the active runtime and distinguishes a missing key from stale, rejected, or partially available internal capabilities.
- Diagnostic bundles now redact common secrets, bearer tokens, Hugging Face tokens, private LAN IPs, hostnames, local usernames, and home paths before writing archive entries.
- Lemonade provider HTTP calls no longer inherit proxy environment settings when contacting the configured Lemonade server.
- Roadmap P0 statuses updated to reflect implemented scope and remaining maintenance tasks.
- Diagnostic bundle sanitization preserves non-secret token counters and boolean configured flags.
- Log parsing now treats expected AMD-machine NVIDIA detection failures and low-level `W:` lines as warnings instead of hard errors.
- Logs & Stats now keeps backend/update events as filtered log entries instead of showing a duplicate summary panel, and abbreviates the performance level label to `PERF`.
- Dashboard and Backends views now consume the backend-owned readiness contract and distinguish loading, unavailable, empty, and populated states.
- Removed the inert global polling control from Settings; health, dashboard, diagnostics, and hardware retain subsystem-specific refresh behavior.
- Backend timestamps now use timezone-aware UTC values for current Python compatibility.
- Renamed local Request Defaults to LCC Workflow Defaults and applied them to smoke-test requests and Bench Lab quick-test initialization.
- Smoke Test now uses the core CompletionRunner directly; BenchRunner is limited to prompt adaptation, suite orchestration, aggregation, and storage.
- Run Evidence detail and Markdown exports now include the Lemonade logs emitted during the recorded operation window.
- Run Evidence list/detail views and JSON/Markdown exports now expose available runtime, profile, and model identity while diagnostic summaries omit sensitive server URLs and request content.
- Profile, direct-load, Smoke Test, and Bench Lab surfaces now make the applied workflow profile explicit before actions.
- Bench Lab results now preserve full prompts, outputs, reasoning, request settings, runtime identity, process/memory evidence, and operator assessments.
- Run Evidence now correlates provider samples at operation start/end and explicitly labels accelerator ownership as unproven.
- Hugging Face inspection, profile creation, and explicit pull are separate steps; Lemonade remains responsible for registration, download, import, and updates.
- Container documentation distinguishes API reachability from host telemetry and keeps PID/sysfs/device exposure explicit and opt-in.
- Public documentation now clarifies that LCC can be used directly on its Linux host, through an SSH tunnel, or deliberately over a trusted LAN; the maintainer's remote workflow is not a deployment requirement.
- Project-status documentation now identifies Bench Lab as functional but still early-stage, with its presentation, suite library, and analysis workflow expected to evolve.
- Container delivery status now records the merged packaging work and the current Podman validation boundary without claiming native Docker Compose testing on the development host.

### Fixed

- Completion streaming now closes every `httpx` response explicitly and accepts metadata/reasoning chunks where `delta.content` is null.

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
