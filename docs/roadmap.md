# Roadmap

Lemonade Control Center is a guided graphical operator console for Lemonade. It is not a chat UI and it is not a replacement for official Lemonade tools.

The roadmap is organized around one rule:

```text
Make Lemonade easier to operate, then make the runtime behavior easier to prove.
```

## Current Execution Plan

Last reviewed: 2026-07-13

This section is the canonical handoff for ongoing implementation. The P0/P1/P2 sections below explain product direction and scope; this section defines the order in which the remaining work should be completed.

### Current Delivery State

- P0 operator basics are complete. See [P0 Closeout](./p0-closeout.md).
- Backend Readiness V1, LCC Workflow Defaults, and the shared CompletionRunner foundation are implemented on `main`.
- Run Evidence viewer, detail API, filters, JSON/Markdown export, and operation-window journal correlation are implemented on `main` through merged pull request [#11](https://github.com/peppeg/Lemonade_Control_Center/pull/11).
- Run Evidence Identity Linkage is implemented and merged on `main` through pull request [#12](https://github.com/peppeg/Lemonade_Control_Center/pull/12).
- Workflow Profiles and Workflow Memory are implemented and merged on `main` through pull request [#13](https://github.com/peppeg/Lemonade_Control_Center/pull/13).
- Bench Lab workflow comparison is implemented and merged on `main` through pull request [#14](https://github.com/peppeg/Lemonade_Control_Center/pull/14).
- Telemetry Providers and Accelerator Evidence are implemented and merged on `main` through pull request [#15](https://github.com/peppeg/Lemonade_Control_Center/pull/15).
- Guided Hugging Face Intake is implemented and merged on `main` through pull request [#16](https://github.com/peppeg/Lemonade_Control_Center/pull/16).
- LCC container packaging is implemented and merged on `main` through pull request [#17](https://github.com/peppeg/Lemonade_Control_Center/pull/17). The image was built and exercised with Podman on the development host; native Docker Compose validation remains welcome on systems with Docker and the Compose plugin installed.
- The 0.3.0 UI and operations closeout is implemented and merged on `main` through pull request [#18](https://github.com/peppeg/Lemonade_Control_Center/pull/18). It includes the cross-page UI review, clearer diagnostics, guarded backend install/update operations, documentation refresh, and final validation against Lemonade Server 10.9.0.
- [LCC 0.3.0](https://github.com/peppeg/Lemonade_Control_Center/releases/tag/0.3.0) was released on 2026-07-13. Steps 0–6 below describe the delivered 0.3.0 foundation; step 7 is the next ordered product block.
- Existing evidence records remain backward compatible. Records created before journal or identity linkage show those optional fields as unavailable.

### Execution Order

#### 0. Close The Current Run Evidence Delivery

Status: complete

Done when:

- a new smoke test appears in the Run Evidence workspace;
- a new load attempt appears with requested and observed runtime state;
- a new record shows correlated Lemonade journal entries or an honest unavailable/error state;
- kind, result, and text filters behave correctly;
- JSON and Markdown downloads contain the selected record;
- pull request #11 is merged after manual validation.

#### 1. Complete Run Evidence Identity Linkage

Status: complete

Goal:

```text
Tie every useful record to the runtime and workflow intent that produced it.
```

Scope:

- persist the active LCC runtime id, label, and normalized server URL;
- persist the selected workflow profile id/name when an action uses one;
- distinguish requested model identity from observed/canonical model identity where available;
- keep old evidence files readable through optional fields and tested defaults;
- expose identity fields in list/detail views and JSON/Markdown exports;
- keep diagnostic summaries free of prompt, response, stop-sequence, and sensitive server data.

Done when backend tests prove persistence, legacy compatibility, filtering/detail behavior, export behavior, and diagnostic redaction.

#### 2. Consolidate Workflow Profiles And Workflow Memory

Status: complete

Goal:

```text
Store why a configuration exists, not only which flags it contains.
```

Scope:

- connect model, runtime, load options, LCC Workflow Defaults, notes, and known caveats;
- attach the latest useful Run Evidence result to a profile without copying full evidence into profile storage;
- make profile application explicit before load, smoke, or Bench Lab actions;
- preserve the boundary between Lemonade-owned runtime options and LCC-owned request defaults;
- support practical intents such as Coding Fast, Coding Long Context, Review Heavy, Italian Writing, Agent Fallback, and Stress Test.

Done when a profile can be selected, applied, traced into new evidence, and revisited with its last useful result.

#### 3. Mature Bench Lab On The Shared Foundations

Status: complete

Goal:

```text
Compare real workflows and preserve enough evidence to explain the result.
```

Scope:

- keep CompletionRunner as the only completion transport;
- keep BenchRunner focused on prompt adaptation, suite orchestration, aggregation, and storage;
- add coding-agent-oriented suites rather than duplicating `lemonade bench`;
- preserve prompts, outputs, reasoning, metrics, runtime/profile identity, and resource evidence;
- add manual quality scores and notes;
- compare models and profiles;
- export readable comparison reports.

Done when two profile/model combinations can run the same workflow suite and produce an inspectable comparison report.

#### 4. Add Telemetry Providers And Accelerator Evidence

Status: complete

- formalize the built-in Linux process/sysfs sampler as a provider;
- add optional `xdna-top` and `amdgpu_top` providers when installed;
- correlate provider samples with Run Evidence windows;
- label every metric as measured, inferred, unavailable, unsupported, or degraded;
- avoid claiming accelerator ownership when the available telemetry cannot prove it.

#### 5. Add Guided Hugging Face Intake

Status: complete

- inspect repository and variant relevance without becoming a marketplace;
- check GGUF/ONNX applicability and likely memory impact;
- create or update a workflow profile;
- offer an optional smoke test and follow-up Run Evidence or Bench Lab workflow;
- continue using Lemonade for pull/import and update ownership.

#### 6. Package LCC For Easier Deployment

Status: complete

- provide an LCC web/API container image;
- provide a compose example for host or remote Lemonade;
- document `/proc`, `/sys`, `/dev/dri`, `/dev/accel`, PID namespace, and privilege limitations;
- never imply that container deployment provides host telemetry that is not actually mounted or reachable.

#### 7. Extend To Multi-Host And Agent Readiness

Status: later P2 work

- distinguish API-only targets, LCC-on-host targets, SSH collectors, and a possible collector service;
- add readiness checks for OpenAI-compatible clients and, where applicable, Anthropic Messages/vLLM clients;
- include reachability, loaded model, context, latency, and recommended profile evidence;
- do not confuse successful API reachability with trusted host telemetry.

### Parallel Maintenance Lane

- Add persistent model-download progress and reconnectable job state for long Hugging Face pulls. Prefer Lemonade-owned `/v1/downloads` jobs (`stream=true`, `subscribe=false`) so progress survives page refreshes; do not move download ownership into LCC.

These tasks should be handled when relevant but should not interrupt the execution order without a concrete compatibility or safety issue:

- manually review official Lemonade Web UI/App changes and update the overlap matrix;
- add dated compatibility fixtures when Lemonade changes `/v1/system-info` or completion streaming;
- update [Tested Environment](./tested-environment.md) only after real smoke testing;
- review real diagnostic bundles before public sharing;
- rank Backend Readiness alerts by hardware/profile relevance after profile linkage exists;
- deepen trusted/manual server management if remote API-only targets become common.

### Validation Policy

- Backend behavior, persistence, compatibility, parsing, redaction, and export contracts require automated tests.
- Frontend changes require `svelte-check` and a production build.
- Visual and workflow validation is performed manually in the running application by the operator; Playwright is not part of the current default validation flow.
- Real Lemonade smoke tests remain necessary for version compatibility claims and updates to `docs/tested-environment.md`.
- Do not start or leave LCC running automatically; the operator starts it explicitly, commonly through a Windows-to-Linux SSH workflow.

### Implementation Map

- Run Evidence schemas: `backend/app/models/schemas.py`
- Run Evidence storage, capture, and export: `backend/app/services/run_evidence.py`
- Journal parsing and window collection: `backend/app/services/log_parser.py`
- Run Evidence and Smoke Test API: `backend/app/routers/lemonade.py`
- Run Evidence backend tests: `backend/tests/test_run_evidence.py`, `backend/tests/test_log_parser.py`, `backend/tests/test_api.py`
- Run Evidence workspace: `frontend/src/routes/evidence/+page.svelte`
- Frontend API/types: `frontend/src/lib/api/client.ts`, `frontend/src/lib/types/index.ts`
- Shared completion transport: `backend/app/services/completion_runner.py`, `backend/app/models/completions.py`
- Completion transport tests: `backend/tests/test_completion_runner.py`
- Existing profile backend: `backend/app/models/profiles.py`, `backend/app/services/profile_service.py`, `backend/app/routers/profiles.py`
- Existing profile frontend: `frontend/src/lib/stores/profiles.ts`, `frontend/src/routes/models/[name]/+page.svelte`
- Bench Lab orchestration: `backend/app/services/bench/`, `backend/app/routers/bench.py`
- Bench Lab frontend: `frontend/src/routes/bench/+page.svelte`
- Backend Readiness: `backend/app/services/backend_readiness.py`, `frontend/src/routes/backends/+page.svelte`
- Diagnostic summary/redaction: `backend/app/services/diagnostic_bundle.py`
- Manual development checks: [Development](./development.md)
- Product overlap decisions: [Overlap Matrix](./overlap-matrix.md)
- Delivered changes: [Changelog](../CHANGELOG.md)

## P0: Direction And Operator Basics

P0 is about making the product direction concrete and removing ambiguity around overlap with official Lemonade tooling.

P0 closeout details are tracked in [P0 Closeout](./p0-closeout.md).

Recommended order:

1. Positioning and overlap discipline.
2. Connection Doctor.
3. Guided Load v2.
4. Diagnostic Bundle and sanitization review.
5. Manual official Web UI/App audit.

### Positioning

Status: P0 implemented

- Describe LCC as a guided operator console.
- Keep the "not a chat interface" boundary.
- Be explicit that official Lemonade UI/CLI are capable and remain the baseline.
- Document where LCC overlaps and where it must differentiate.

### Overlap Matrix

Status: P0 implemented, keep updated as Lemonade evolves

- Track Lemonade UI/CLI coverage.
- Track LCC coverage.
- Decide keep, cut, or differentiate.
- Use the matrix to prevent lazy duplication.

### Connection Doctor

Status: P0 implemented, P1 can deepen trusted server workflows

Goal:

```text
Find Lemonade, validate the connection, explain what is reachable, and make the active target obvious.
```

Target scope:

- HTTP health checks for configured runtimes. V0 is implemented for Lemonade runtimes.
- Better connection summary in Settings and Setup. V0 is available in Settings for the active runtime.
- Clear distinction between local host telemetry and remote API-only targets. V0 distinguishes local targets from remote/API-only targets.
- Trusted server groundwork.
- UDP beacon discovery and HTTP fallback probes. V0 is implemented in the setup flow.
- URL normalization when a user pastes `/api/v1` or `/v1`. V0 is implemented.
- Warnings when host telemetry cannot be trusted for a remote target. V0 is implemented.

P1 candidates:

- Promote trusted/manual server selection from setup discovery into the settings workflow.
- Add remote host collectors if API-only targets become common.

### Guided Load V2

Status: P0 implemented

Goal:

```text
Make load, unload, pull, and profile use visible, guarded, and explainable.
```

Target scope:

- Keep model inventory operational, not marketplace-oriented.
- Show downloaded vs catalog vs loaded state clearly.
- Show profile/load consequences before action. V0 operator preflight is implemented in the load dialog.
- Keep advanced args available but validated. Frontend and backend block Lemonade-managed llama.cpp args.
- Use Lemonade 10.9 compatibility notes for reserved args and context defaults.
- Show backend requested vs backend observed after load when possible. V0 post-load notification and load dialog result panel include observed backend/context/PID when process evidence is available.
- Show RAM/swap risk before and after load. V0 estimates planning headroom and context risk from hardware/process/model size data.
- Offer a small smoke test, not a chat UI. V0 is implemented from the active model panel.
- Save first evidence hooks for future Run Evidence. V0 stores smoke-test and load-attempt evidence locally.

P1 candidates:

- Attach load evidence to named workflow profiles.
- Compare load evidence across repeated attempts.

### Diagnostics Bundle V1

Status: P0 implemented, keep reviewing real bundles before public sharing

Goal:

```text
Create a useful operator/support snapshot without exposing secrets.
```

Target scope:

- Lemonade version and health.
- LCC version and capabilities.
- OS/kernel/hardware summary.
- systemd status and recent logs when available.
- RAM/swap/disk/process snapshot.
- Loaded model and load options when available.
- Sanitized settings. V1 redacts common secrets, tokens, private LAN IPs, hostnames, usernames, and home paths.
- Bundle manifest and README. V1 is implemented.
- Local target snapshot without live Lemonade API dependency. V1 is implemented.
- Recent Run Evidence summary without prompt/response bodies. V1 is implemented.

### Privacy And Sanitization

Status: P0 implemented, best-effort redaction plus user review requirement

Goal:

```text
Make exported diagnostics useful without leaking secrets or personal host details.
```

Target scope:

- Redact LCC and Lemonade API keys.
- Redact environment secrets and tokens.
- Avoid committing or exporting raw local probe results by default.
- Review local usernames, paths, LAN IPs, hostnames, and model paths before public support artifacts. V1 performs best-effort redaction and warns the user to review the archive.
- Make the diagnostic bundle suitable for GitHub issues after review.

### Official Web UI/App Audit

Status: P0 docs/API audit completed, manual screenshot-level audit remains a maintenance task

Goal:

```text
Verify what the official Web UI/App actually covers so LCC does not invest in weak duplication.
```

Audit targets tracked:

- pin/unpin UX
- backend install/uninstall UX
- config editing depth
- log filtering/parsing depth
- benchmark UI coverage
- system stats/storage UI coverage
- Hugging Face variant/update UX
- cloud provider UX

### Compatibility Discipline

Status: P0 implemented as process documentation

Goal:

```text
When Lemonade changes, know what LCC depends on and test it deliberately.
```

Artifacts:

- private compatibility contract and upgrade-audit template maintained outside the public repository
- dated private upgrade audit notes
- capability probe
- tested-environment updates after smoke tests

## P1: Workflow Memory And Run Evidence

P1 adds the parts that make LCC more than a nicer control surface.

### Profiles

Goal:

```text
Store human workflow intent, not only backend flags.
```

Examples:

- Coding fast
- Coding long context
- Review heavy
- Italian writing
- Agent fallback
- Stress test

Profiles should connect model, target server, load options, LCC workflow defaults, notes, known caveats, and last useful result. Workflow defaults apply only to requests initiated by LCC; external clients retain their own request configuration.

### Hugging Face Model Intake

Goal:

```text
Turn a model repo into a checked, profiled, testable Lemonade setup.
```

This should not be a generic Hugging Face browser. Lemonade already handles model pull/import and the official UI has update detection.

LCC should add:

- repo/variant inspection
- GGUF/ONNX relevance checks
- likely memory impact
- profile creation
- optional smoke test
- follow-up Bench Lab or Run Evidence

### Run Evidence V0

Status: V0 viewer, export, and log-window correlation implemented; server/profile linkage remains

Goal:

```text
For one request window, save what was run and what the machine did.
```

Initial evidence:

- server, model, profile, backend/context/options
- prompt and full output. V0 stores this for smoke tests.
- TTFT, tokens/sec, token counts. V0 stores this for smoke tests.
- finish reason and truncation confidence. V0 stores this for smoke tests.
- RAM/swap/process snapshot. V0 stores this for smoke tests when available.
- LCC workflow defaults used for a smoke test. V0 records max tokens, temperature, timeout, and stop sequences; diagnostic summaries omit stop-sequence content.
- shared completion evidence records endpoint, metric provenance, reasoning separately from final text, protocol warnings, and structured error kinds.
- list/detail viewer with model, kind, outcome, runtime, request, response, reasoning, and warning inspection. V0 is implemented.
- relevant Lemonade journal logs in the run window, with explicit unavailable and capture-error states. V0 is implemented.
- JSON/Markdown export. V0 is implemented per run.

### Backend Readiness And Updates

Status: P1 V1 implemented; hardware/profile relevance remains a follow-up

Goal:

```text
Show which Lemonade backends are installed, installable, unsupported, or need updates before the user tries to load a model.
```

Primary source of truth:

- Lemonade `/v1/system-info`
- `recipes[*].backends[*].state`
- backend `message`, `action`, `version`, `release_url`, `download_filename`, and `devices`

Observed on Lemonade `10.9.0`:

- `llamacpp:vulkan` can report `installed` with a concrete llama.cpp build version.
- `llamacpp:rocm` can report `update_required` with an operator action such as `lemonade backends install llamacpp:rocm`.
- other recipe/backend pairs can report `installable` or `unsupported` with device and OS context.

V1 includes:

- a backend-owned, typed normalization layer for `/v1/system-info` readiness data;
- a Dashboard summary and dedicated Backends page for installed, update-required, installable, unsupported, and unknown states;
- clear separation between authoritative readiness data and historical backend/update events in logs;
- release links, download filenames, and copied operator commands when Lemonade provides them;
- a best-effort `backend_readiness.json` entry in diagnostic bundles.
- confirmed install/update actions for authoritative `installable` and `update_required` entries through Lemonade's public `/v1/install` API, always with `force=false` and without shell execution.

Follow-up scope:

- rank or alert update-required backends by relevance to current hardware and selected workflow profiles;
- preserve dated compatibility fixtures when Lemonade changes the system-info contract.

Out of initial scope:

- automatic or unattended backend updates;
- backend uninstall;
- replacing the official backend installer UI.

Any future uninstall action may use Lemonade `/v1/uninstall`, but it must be gated, explicit, and treated as a potentially disruptive operator action.

### Telemetry Provider Abstraction

Goal:

```text
Let LCC correlate optional hardware telemetry without owning every low-level metric.
```

Initial providers:

- built-in Linux process/sysfs sampler
- `xdna-top`, if installed
- `amdgpu_top`, if installed

Every metric should be labeled honestly as measured, inferred, unavailable, unsupported, or degraded.

### Docker Image

Goal:

```text
Make LCC easier to run without promising impossible container telemetry.
```

Initial target:

- LCC web/API image
- compose example for connecting to host or remote Lemonade
- clear notes about `/proc`, `/sys`, `/dev/dri`, `/dev/accel`, host PID, and privileged/device-specific telemetry limits

## P2: Bench Lab And Advanced Evidence

P2 is where LCC becomes a deeper operator and comparison tool.

### Bench Lab

Goal:

```text
Benchmark real workflows, not only model speed.
```

Lemonade already has `lemonade bench`. LCC Bench Lab should focus on:

- coding-agent-oriented suites
- full prompt/output preservation
- manual quality scores and notes
- resource correlation
- profile comparison
- diagnostic/report export

### Accelerator Evidence UI

Goal:

```text
Show whether a run produced credible CPU/iGPU/NPU evidence.
```

Use cautious language:

- NPU activity detected in the run window
- iGPU busy averaged X during the run
- process PID owned an accelerator context

Avoid claims that cannot be proven by the telemetry provider.

### Multi-Host And Remote Collector

Goal:

```text
Support Corsaro/Gigio/local workflows without confusing API reachability with host telemetry.
```

Possible levels:

- API-only remote target
- LCC running on the Lemonade host
- SSH-based collector
- small LCC collector service

### Agent Readiness

Goal:

```text
Tell the user whether Lemonade is ready for Codex, Pi, Claude Code, or similar tools.
```

Potential checks:

- server reachable
- model loaded
- OpenAI-compatible chat completion smoke
- Anthropic Messages/vLLM readiness where applicable
- context and latency sanity
- recommended profile

## Not On The Roadmap For Now

- Chat UI
- alternative model marketplace
- full official UI clone
- long-term observability platform
- full terminal UI
- owning low-level AMD telemetry directly

These may be integrated around the edges, but they should not become LCC's product identity.
