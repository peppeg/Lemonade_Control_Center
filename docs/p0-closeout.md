# P0 Closeout

> Historical snapshot: this document records what was complete or deferred when P0 closed. For current delivery status and execution order, use the [Roadmap Current Execution Plan](./roadmap.md#current-execution-plan).

P0 focused on making Lemonade Control Center clear, defensible, and useful as an operator console.

LCC is an independent, unofficial companion for Lemonade. It is not a replacement for the official Lemonade Web UI, not a chat client, and not a model marketplace.

## Done Criteria

P0 is considered complete when LCC can:

- explain its relationship to official Lemonade tools;
- discover and validate a Lemonade runtime;
- guide model load operations with preflight risk signals;
- record what happened during load and smoke-test flows;
- export a sanitized local diagnostic bundle;
- document where official Lemonade overlap is accepted, avoided, or differentiated.

## Implemented

### Positioning

Public docs describe LCC as a guided operator console. The README and roadmap explicitly state that official Lemonade tools remain the baseline.

### Overlap Discipline

The public overlap matrix separates Lemonade CLI, official Web UI/App, and API overlap.

Rules:

- CLI overlap is acceptable when LCC turns commands into guided, repeatable workflows.
- Web UI/App overlap requires a clear operator-console differentiator.
- API overlap is expected because LCC should use Lemonade as the source of truth.

### Connection Doctor

Connection Doctor validates configured Lemonade runtimes, normalizes common URL suffixes, distinguishes local from remote/API-only targets, reports host telemetry applicability, records process evidence where available, and recommends a next action.

Setup also supports Lemonade server discovery through UDP beacons and HTTP fallback probes.

### Guided Load V2

The load dialog now provides:

- model size and memory headroom;
- context risk estimate;
- active process impact;
- saved Lemonade defaults;
- Lemonade-managed argument validation;
- requested versus observed backend/context;
- PID, RSS, RAM delta, duration, and evidence id;
- observed command line when available.

### Run Evidence Seed

LCC records local evidence for:

- load attempts;
- post-load smoke tests.

Evidence includes model, requested options, observed process/backend/context, timing, token metrics where available, memory snapshots, warnings, and result state.

### Diagnostics Bundle V1

Diagnostic bundles are local-first and do not require live Lemonade API calls to complete. Bundles include manifest, README, target snapshot, hardware, service/process state, recent logs, last-task parsing, capabilities, and Run Evidence summary.

Sanitization is best effort. LCC redacts common secrets, bearer tokens, Hugging Face tokens, private LAN IPs, hostnames, local usernames, and home paths before writing bundle entries. Users are still instructed to review archives before public sharing.

### Compatibility Discipline

The repo documents tested Lemonade versions publicly and keeps compatibility contract/audit notes outside git for local planning.

## Official Lemonade Audit Notes

Sources reviewed:

- Lemonade CLI docs: https://lemonade-server.ai/docs/guide/cli/
- Lemonade API docs: https://lemonade-server.ai/docs/api/lemonade/
- Lemonade configuration docs: https://lemonade-server.ai/docs/guide/configuration/
- Lemonade Web UI development docs: https://lemonade-server.ai/docs/dev/web-ui/

Confirmed official coverage from docs:

- CLI covers status, logs, backends, scan, telemetry, list, pull, import, delete, load, unload, pin, unpin, export, run, and bench.
- `lemonade run MODEL_NAME` loads a model and opens the web app.
- `lemonade logs` opens server logs in the web UI.
- `pull` supports registered models, Hugging Face repos, explicit variants, custom model registration, and omni-model components.
- `load` supports context size, backend choice, backend args, merge/no-merge args, saved options, and pinning.
- `bench` benchmarks chat completion performance across models, backends, context sizes, scenario files, JSON output, and comparison mode.
- The API exposes model files, health, stats, system stats, system info, install/uninstall, model management, download/job surfaces, and pull variants.
- The web app exists under Lemonade's `/app` flow and shares React code with the desktop app.

Additional local check on Lemonade `10.9.0`:

- `/v1/system-info` exposes backend readiness state under `recipes[*].backends[*]`, including `state`, `message`, `action`, `version`, `release_url`, `download_filename`, and `devices`.
- This makes `/v1/system-info` the preferred source of truth for LCC backend readiness and update prompts.
- Recent logs remain useful as timeline evidence, but should not be the only way LCC detects backend install/update state.
- `/v1/install` and `/v1/uninstall` are documented mutating endpoints and should only be used behind explicit operator confirmation if LCC ever exposes them.

P0 conclusion:

LCC should avoid becoming a chat client, generic model marketplace, official config clone, or long-term telemetry platform. It should continue investing in guided operations, host/process context, diagnostics, workflow memory, and run evidence.

## Deferred To P1

- Trusted/manual server management beyond setup discovery.
- Run Evidence list/detail viewer. Delivered during P1; see the current roadmap status.
- Workflow profiles that attach intent and notes to evidence.
- Hugging Face intake that checks compatibility and creates profiles without becoming a marketplace.
- Optional telemetry providers such as `xdna-top` and `amdgpu_top`.
- Docker image and compose guidance with clear host-telemetry limitations.

## Deferred To P2

- Bench Lab workflow suites.
- Accelerator Evidence UI.
- Multi-host collector architecture.
- Agent readiness checks for Codex, Pi, Claude Code, and similar tools.
