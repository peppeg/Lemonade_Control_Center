# Roadmap

Lemonade Control Center is a guided graphical operator console for Lemonade. It is not a chat UI and it is not a replacement for official Lemonade tools.

The roadmap is organized around one rule:

```text
Make Lemonade easier to operate, then make the runtime behavior easier to prove.
```

## Current Execution Plan

Last reviewed: 2026-11-23

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
- [LCC 0.3.0](https://github.com/peppeg/Lemonade_Control_Center/releases/tag/0.3.0) was released on 2026-07-13. Steps 0–6 below describe the delivered 0.3.0 foundation.
- Post-0.3.0 maintenance on `main` (pull requests #20–#34) added Lemonade 11.x compatibility fixes (11.7 telemetry parsing, nested config keys, `recipe_options` from the models API), AMD GTT/VRAM telemetry, the `lemonade_exposed` diagnostic, Authorization forwarding to Lemonade, and reasoning-model Smoke Tests. See the [Changelog](../CHANGELOG.md).
- A code audit on 2026-11-09 found access-control and hardening gaps, re-verified against the code on 2026-11-12. Step 7 (Security And Maintenance Hardening) is in progress; 7.1, 7.2, and 7.4 are merged. Steps 8–10 follow in order: long-run performance history (adopted from a contributor fork), Bench Lab v2, then multi-host and agent readiness. Step 7 must land first, because every later step adds endpoints, stored state, or remote surface that those gaps affect.
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

#### 7. Security And Maintenance Hardening

Status: in progress

Goal:

```text
Make every LCC entry point enforce the same access rules, and keep secrets and generated state under control.
```

Work is split into small pull requests. Each item lists what is done when it lands.

Recommended order: 7.1 → 7.2 → 7.4 (small, and they close the access-control holes) → 7.3 → 7.5. 7.6 and 7.7 are independent and can run in parallel. Cut a 0.3.1 security release once 7.1–7.4 are merged.

##### 7.1 One access-control path for HTTP and WebSocket

Status: merged in [#40](https://github.com/peppeg/Lemonade_Control_Center/pull/40) on 2026-11-23

- HTTP requests and WebSocket handshakes share one access decision in `services/security.py`. Every WebSocket route calls `authorize_websocket()` before `accept()`.
- Handshakes with a foreign `Origin` are refused. Accepted: the request host, the development origins, and `ALLOWED_ORIGINS`, added for reverse proxies that do not forward the original `Host`. A missing `Origin` (CLI clients) is accepted.
- The tests run against every WebSocket route found in the app, so a new route that skips the helper fails them.

##### 7.2 Reject cross-site requests on mutating methods

Status: merged in [#41](https://github.com/peppeg/Lemonade_Control_Center/pull/41) on 2026-11-23

- The access-control middleware refuses `POST`, `PUT`, `PATCH`, and `DELETE` requests from another site with 403, for loopback and LAN clients alike and on every path. Refusals are written to the audit log.
- When the browser sends `Sec-Fetch-Site`, only `same-origin` and `none` are accepted. Pages cannot forge it, so proxies that rewrite `Host` keep working without configuration. This replaces the original plan to always compare `Origin`.
- Without it, `Origin` must match the request host. Development origins and `ALLOWED_ORIGINS` are accepted in both cases, and CLI clients are unaffected.
- A test enumerates the app routes and checks every mutating one against a stand-in handler.

##### 7.3 Protect local secrets and state files

Status: in review, [#45](https://github.com/peppeg/Lemonade_Control_Center/pull/45)

- Every state writer uses `services/state_files.py`: a temporary file in the same directory, `fsync`, and `os.replace`, with mode `0600`.
- The data directory is created with mode `0700`. On startup an existing one is tightened, together with `config.json`.
- `audit.jsonl` is rotated at 5 MB, keeping three older files.
- A test fails if another module writes files directly.
- Later steps that add SQLite files (8, 9) must create them with the same modes.

##### 7.4 Reverse proxy trust (opt-in)

Status: merged in [#42](https://github.com/peppeg/Lemonade_Control_Center/pull/42) and [#43](https://github.com/peppeg/Lemonade_Control_Center/pull/43) on 2026-11-23

- Localhost trust covers direct connections only. A request with `X-Forwarded-For`, `Forwarded`, or `X-Real-IP` always needs the key, whatever address it resolves to, however LCC is started.
- `app/run.py` passes explicit proxy options instead of Uvicorn's defaults. `TRUSTED_PROXY_IPS`, empty by default, lists the proxies whose `X-Forwarded-For` is recorded as the client address. It never grants trust.
- This differs from the original plan, which only disabled forwarded headers by default. Clients of a same-host proxy would then all have looked local and needed no key.
- A warning explains once why a proxied setup asks for a key.
- Added to the original scope (#43): localhost trust also requires LCC to be opened as `localhost`, an IP address, or a name in `ALLOWED_HOSTS`, which closes DNS rebinding.
- The Reverse Proxy section of [Security](./security.md) documents both modes.

##### 7.5 Reliability and visibility

- Replace silent `except Exception: pass` blocks (12 today, metrics collector loop first) with logged warnings, rate-limited where a loop could flood the log. Review the other broad `except Exception` handlers (15 files) and narrow them where the expected errors are known.
- Share one `httpx.AsyncClient` per Lemonade runtime instead of creating one per call (12 call sites in `providers/lemonade.py`, `services/completion_runner.py`, `services/setup.py`, `services/huggingface_intake.py`, `routers/health.py`), keeping `trust_env=False`. Close and recreate the client when the active runtime, URL, or key changes.
- Move blocking file I/O in async handlers (config save, Run Evidence, Bench storage) off the event loop where it can be slow. `routers/logs.py` uses a blocking `subprocess.Popen` inside the WebSocket handler; move it to `asyncio.create_subprocess_exec`.
- Add a shared rate-limited logging helper here; step 8 reuses it for the metrics-history loops.

Done when collector failures are visible in the LCC log and existing tests still pass.

Size: M. It can be split into logging, HTTP client, and async I/O pull requests.

##### 7.6 Release and supply-chain hygiene

- Keep the version in one source and derive the others (`backend/app/config.py`, `backend/pyproject.toml`, `frontend/package.json`).
- Remove the duplicated `backend/requirements.txt` dependency list, or generate it from `pyproject.toml`, and add a lock file so the container build is reproducible.
- Add `SECURITY.md` with a private disclosure channel, Dependabot for pip, npm, and GitHub Actions, and `pip-audit` in CI.
- Make `capabilities/probe.py` write `results/` and `CAPABILITIES.md` relative to its own directory instead of the current working directory, so running it from the repository root no longer leaves untracked files there.

Done when CI fails on a version mismatch or a known-vulnerable dependency.

Size: M. Independent of 7.1–7.5; it can run in parallel.

##### 7.7 Host scope: never mislabel telemetry

Pulled forward from step 10 on 2026-11-12. Remote runtimes are already in use, and today LCC shows its own host's data for them.

- Host-local features always read the LCC host, whatever the active runtime is:
  - telemetry (`services/telemetry.py`, `services/metrics/`);
  - process evidence (`find_llama_server` in `services/process.py`);
  - the journal (`routers/logs.py`, `services/metrics/task_history.py`);
  - `systemctl` status and restart;
  - diagnostics collectors.

  With a remote active runtime, LCC presents its own RAM, GPU, process, and journal as the target's.
- Derive a `host_scope` per runtime, `same_host` or `remote`: loopback and the LCC host's own addresses count as `same_host`, plus the container's host gateway when host telemetry is mounted. Allow a manual override in Settings for unusual setups.
- Every host-local feature checks the active runtime's scope. When it is `remote`, it shows "not available for a remote target" instead of local data.
- Run Evidence and Bench results record `host_scope` and the telemetry source. Records from a remote target never include LCC-host telemetry. Older records stay readable, with the field shown as unknown.
- Redefine `access_mode` (`local`, `ssh_tunnel`, `tailscale`, `remote`; stored but unused today) as a transport hint only, with no effect on trust or scope. An SSH tunnel makes a remote host look like `localhost`, so a runtime with `access_mode=ssh_tunnel` is treated as `remote` even on a loopback URL.

Done when switching the active runtime to a remote URL never shows LCC-host data as the target's, and tests cover both scopes for each host-local feature, including the SSH-tunnel case. Size: M. It can be developed in parallel with 7.3–7.6, because it touches different code.

Known and accepted for now:

- The browser keeps the LCC key in `localStorage` and passes it as `lcc_key` in the WebSocket URL, because browsers cannot set headers on WebSocket connections. Revisit if LCC moves to cookie sessions.

#### 8. Long-Run Performance History

Status: backend in review, [#38](https://github.com/peppeg/Lemonade_Control_Center/pull/38)

Goal:

```text
Keep inference performance and hardware history across LCC restarts, and plot it honestly.
```

Source: [@dolaresko](https://github.com/dolaresko) developed this on a fork and opened [#38](https://github.com/peppeg/Lemonade_Control_Center/pull/38) on 2026-11-23. The pull request was then reduced to the backend (8.1–8.3); the History view (8.4) follows in a separate one.

The block descriptions below double as the review checklist for these pull requests.

Today task history is a `deque(maxlen=50)` saved to `data/task_history.json`, and hardware history lives in RAM for 30 minutes.

##### 8.1 Reject unmeasurable generation rates

- Lemonade reports `gen_tps = 1000000.0` for one-token tasks, because there is no measurable interval. LCC stores it, and one such point flattens every chart.
- Port `_measurable_rate()`: rates for fewer than 2 output tokens, or above a plausibility ceiling, become "not measured". The record is kept for TTFT and token counts.
- Port the parser tests and the Lemonade 11.7 journal fixture from the fork.

Done when no stored or displayed rate comes from a sentinel value, and the existing parser tests still pass. Size: S. It can land on its own, before the rest of step 8.

##### 8.2 SQLite metrics store

- Port `services/metrics/store.py`: standard-library `sqlite3`, WAL mode, `synchronous=NORMAL`, tables `task_records`, `hardware_samples` (per-minute rollups with mean and peak), `metrics_meta` (schema version). Writes go through `asyncio.to_thread`.
- Rebase onto current `main`:
  - keep the model name and log time added to task records by #31;
  - add the AMD VRAM/GTT fields from #30 to the hardware rollup;
  - keep the 11.x telemetry parsing.
- Apply step 7 rules: database file `0600` in the `0700` data directory, and background loops (sampler, rollup, pruner, legacy import) log failures through the 7.5 helper instead of `pass`. Rows record the runtime id and the 7.7 `host_scope`, and hardware rows are written only for `same_host` runtimes.
- Import `data/task_history.json` once, without duplicates, and keep the file as a backup.
- Retention (decided 2026-11-12, replacing the fork's 90/30-day defaults):
  - task records are kept indefinitely by default, with optional retention configurable through `.env`. They are small (a few MB per year in personal use) and are the long-term evidence of how a model's performance changed across Lemonade, driver, and profile updates;
  - per-minute hardware rollups are kept for 30 days, then compacted into hourly rollups (mean and peak) that are kept indefinitely. Per-minute rows are what grows (about 525,000 rows a year); hourly rows are about 9,000 a year;
  - compaction and pruning run on startup and hourly;
  - the UI shows the database size and offers export and clearing by period.

  This keeps model-performance history, not everything that happens on the machine, so it stays outside "long-term observability platform" (see "Not On The Roadmap").
- Port `test_metrics_store.py` and `test_metrics_collector.py`.

Done when history survives an LCC restart, retention pruning is tested, and the legacy import is idempotent. Size: L.

##### 8.3 History API

- Add read endpoints for task series, Y-scale hints, hardware series, history summary, and CSV export of task rows.
- `POST /api/metrics/clear` requires an explicit `scope` (`buffer` or `history`); a missing or unknown scope is rejected. Clearing history becomes destructive, so it relies on the 7.2 cross-site protection and is written to the audit log. The audit log records the path but not the query string, so it cannot yet tell the two scopes apart.
- Port `test_metrics_api.py`.

Done when every new endpoint is covered by the access-control tests from 7.1/7.2 and by API tests. Size: M.

##### 8.4 History view

- Plot generation speed as a scatter by run index, not as a continuous line. Point size follows output tokens, with P50/P95 reference lines and session breaks after a gap of more than 20 minutes. The chart is plain SVG (`SvgScatterChart.svelte`, `utils/chart.ts`), with no chart library.
- Use one ordinal axis across the History view, and show History RAM in GB, as the Live view does.
- Confirm "clear history" with a dialog built on `ModalFrame`, and show what will be deleted.

Done when the History view renders from the new API and `npm run check` and `npm run build` pass. Size: M–L.

#### 9. Bench Lab v2

Status: planned, after step 8

Goal:

```text
Turn Bench Lab from a quick benchmark utility into a benchmark manager: your own prompts and suites, runs that execute in the background, and comparisons you can trust later.
```

Starting point (verified 2026-11-12):

- Five suites are hardcoded in `services/bench/suites.py`. Users cannot create prompts or suites.
- `POST /api/bench/run` executes a whole suite inside one HTTP request (estimated 15 minutes per suite, up to 3600 s per prompt), with no progress, cancel, or recovery.
- Results are JSON lists in `data/bench_results.json`, capped at 100 suite results and 50 quick results.
- Each result record is already rich: runtime and profile identity, observed model, backend, context and PID, RAM and swap before/after, reasoning text, token source, manual score and notes. v2 keeps these fields.
- Bench Lab is disabled by default (`ENABLE_BENCH_LAB=false`).

An earlier standalone prototype (Next.js + SQLite) proved the product shape: a prompt library, suites with ordered prompts, run presets, run detail, and run-to-run comparison. v2 keeps the ideas and the relational data model, not the code.

Design rules:

- LCC stays the only product, and Bench Lab stays a module inside it.
- Execution is owned by the backend. The browser only starts, watches, and cancels runs.
- Runs target the active runtime and the model Lemonade reports as loaded. There is no separate model registry.
- `CompletionRunner` stays the only completion transport.
- Benchmark data lives in its own SQLite file, separate from config and from the metrics history.
- Benchmark real workflows. Do not duplicate `lemonade bench` speed tests.
- Manual quality scoring comes first. Automatic evaluation comes later, if ever.

##### 9.0 Design milestone (documentation only)

- Write `docs/bench-lab.md`: schema, API contract, UI map, run state machine, preset table, and migration of existing results.
- Resolve the open questions below before any code is written.

Done when the design document is reviewed and the open questions are answered.

##### 9.1 Persistence

- `data/bench_lab.db` (`0600`), reusing the connection, WAL, and schema-version pattern from the step 8 store.
- Tables:
  - `prompts` (title, category, system prompt, user prompt, expected behavior, tags, `source` = `builtin` or `user`);
  - `suites` (name, description, recommended context and temperature, `source`);
  - `suite_prompts` (ordered);
  - `runs` (suite, preset, parameters, status, identity, timing, before/after telemetry snapshot, Lemonade and LCC versions);
  - `run_items` (one per prompt: timing, tokens, rates, finish reason, output, reasoning, raw response, error, manual score and notes).
- Seed the current hardcoded suites as read-only `builtin` rows. Users clone them to edit.
- Import `bench_results.json` once as legacy runs and keep the file as a backup.
- Cap the stored raw response size, and allow deleting single runs.

Done when the store is covered by unit tests, including migration and deletion cascade. Size: M.

##### 9.2 Prompt and suite library

- CRUD API for prompts and suites, plus suite prompt ordering, under `/api/bench/`.
- UI tabs: Prompts and Suites, using existing LCC components and `ModalFrame`.
- Export and import a suite as JSON, so suites can be shared without sharing the database.

Done when a user can create a suite from their own prompts and reorder it, and built-in suites cannot be modified in place. Size: M.

##### 9.3 Background run engine

- `POST /api/bench/runs` validates the request and creates a run with status `queued`. A background task executes the prompts one by one through `CompletionRunner` and writes each `run_item` as soon as it completes.
- Only one run executes at a time. A single run can already saturate RAM, GPU, and the loaded model, so a second concurrent run would distort both results. Further requests go into a FIFO queue (decided 2026-11-12).
- The queue is visible in the UI, with each run's position. A queued run can be cancelled before it starts. The queue length is capped (for example 10 runs).
- When a queued run reaches the front, check that the loaded model (and workflow profile) still matches the run. If not, mark the run `skipped` with the reason, keep it in the list, and continue with the next one. The model can change while LCC is running, from another LCC page, the Lemonade CLI, or another client.
- Before each prompt of the executing run, repeat the check. If the model changed mid-run, stop the run with status `failed` and keep the completed items.
- Load, unload, and profile-apply actions in LCC ask for confirmation while a run is executing or queued.
- `GET /api/bench/runs/{id}` returns progress and queue position; the frontend polls it. `POST /api/bench/runs/{id}/cancel` removes a queued run, or stops an executing run after the current prompt.
- The queue does not survive an LCC restart (decided 2026-11-12). This deliberately avoids resuming runs against a model that may have changed while LCC was down. On startup, runs left as `running` become `interrupted` and runs left as `queued` become `cancelled` with the reason "LCC restarted". They stay in the run list with a "Run again" action that reuses their suite, preset, and parameters.
- The old `POST /api/bench/run` stays as a thin wrapper for quick tests until the UI no longer uses it. Quick tests go through the same queue.

States: `queued` → `running` → `completed` | `cancelled` | `failed` | `interrupted`, plus `queued` → `skipped` | `cancelled`.

Done when a full suite runs with the browser closed; three queued runs execute one after another; a model change skips the affected run; progress survives a page refresh; cancel works for queued and executing runs; and an LCC restart leaves no run stuck as `running` or `queued`. Size: L.

##### 9.4 Presets and run context

- Presets set temperature, max tokens, and timeout:

  | Preset | Max tokens | Timeout | Warning |
  |---|---|---|---|
  | Micro | 1,500 | 60 s | |
  | Standard | 4,000 | 180 s | |
  | Hard | 8,000 | 300 s | |
  | Long | 12,000 | 450 s | |
  | Stress | 16,000 | 600 s | yes |
  | Extreme | 32,768 | 900 s | yes |

  Micro, Stress, and Extreme come from the prototype; Standard, Hard, and Long were added on 2026-11-12 and confirmed. All use a default temperature of 0.1, and every value can be overridden per run.
- Warn when max tokens plus the largest prompt exceeds the loaded context size, and when a warned preset is selected.
- Store a `TelemetryManager` snapshot before and after each run (RAM, swap, GPU busy, VRAM/GTT, NPU, temperatures), plus context size, backend, workflow profile, Lemonade version, and LCC version.

Done when every run records its preset, effective parameters, and context, and the warnings are tested. Size: S–M.

##### 9.5 Runs, run detail, and comparison

- UI tabs: Overview, Prompts, Suites, Launch, Runs, Compare.
- Run detail shows each prompt's output, reasoning, metrics, warnings, and manual score and notes.
- Compare two or more runs of the same suite, aligned by prompt, with deltas for TTFT, generation rate, total time, tokens, finish reason, and score.
- Export run and comparison reports as Markdown, CSV, and JSON, reusing the current export code where possible.
- When step 8 is present, link a run to its time window in the performance history.

Done when two model or profile combinations can run the same user-defined suite and produce an inspectable, exportable comparison. Size: L.

##### 9.6 Enable by default

- Enable Bench Lab by default (keeping the switch to turn it off) once 9.1–9.5 are merged and validated on real hardware. Update the README, Development, and Changelog.

Decided on 2026-11-12:

- A run requires its model and workflow profile to be loaded already; it never loads them itself. This keeps the current explicit "apply profile first" rule.
- Presets as in the 9.4 table.
- One run at a time, the others in a FIFO queue that is emptied when LCC restarts (see 9.3).

Open questions for 9.0:

- Polling or the existing WebSocket for progress? (Recommended: polling every 2 s. It is simpler and needs no extra WebSocket route under the 7.1 rules.)
- How much raw response to keep per item? (Recommended: full output and reasoning, raw JSON capped at 256 KB.)

#### 10. Multi-Host And Agent Readiness

Status: planned, after step 9

Goal:

```text
Operate Lemonade servers on other machines without ever presenting the LCC host's data as the target's, and tell the user whether a server is ready for coding agents.
```

Starting point (verified 2026-11-12):

- `config.json` already holds several runtimes, each with a URL, an optional admin key, and an `access_mode` (`local`, `ssh_tunnel`, `tailscale`, `remote`). `access_mode` is stored but no code acts on it.
- Everything that goes through the Lemonade HTTP API already works against a remote URL: models, load and unload, smoke tests, Bench Lab, health, and Authorization forwarding.
- Host-local features always read the LCC host, whatever the active runtime is:
  - telemetry (`psutil`, `/proc`, `/sys`, `amdgpu_top`, `xdna-top` in `services/telemetry.py`);
  - process evidence (`find_llama_server` in `services/process.py`);
  - the journal (`routers/logs.py`, `services/metrics/task_history.py`);
  - service status and restart (`systemctl`);
  - diagnostics collectors and the capability probe.
- With a remote active runtime, LCC can therefore show its own host's RAM, GPU, process, and journal as if they belonged to the target.
- Run Evidence and Bench results already store the runtime id, label, and URL.
- `TelemetryManager` takes a list of providers, which is a natural place for a remote provider.

##### 10.0 Design milestone (documentation only)

- Write `docs/multi-host.md`: target types, the LCC-to-LCC protocol (endpoints, read-only key scope, version handshake), and how 10.2–10.4 build on the host scope from 7.7.

##### 10.1 Host scope

Moved to step 7.7 on 2026-11-12.

##### 10.2 API-only remote targets

- Show a per-target capability summary: which LCC features work through the API alone and which need host access.
- Give each feature that is unavailable for a remote target a clear empty state with the reason, using the same pattern as the container limitations.
- Remote runtimes that use `http://` without an admin key get a diagnostic warning, consistent with the `lemonade_exposed` diagnostic.

Done when every page behaves predictably with a remote active runtime. Size: M.

##### 10.3 Agent readiness

- An "Agent Readiness" check per runtime, stored as a Run Evidence record of kind `readiness`. It checks:
  - reachability and authentication;
  - that a model is loaded;
  - an OpenAI-compatible chat completion, streaming and non-streaming;
  - tool calling, when the model supports it;
  - the Anthropic Messages endpoint, when Lemonade exposes it;
  - context size against a target client profile (for example at least 32k for coding agents);
  - TTFT and generation rate against simple thresholds;
  - the recommended workflow profile.
- Client profiles (Codex, Claude Code, Pi, generic OpenAI-compatible) define the minimum requirements and produce a copyable configuration snippet (base URL, model name, environment variable names). LCC never stores those clients' keys.

Done when a readiness report explains, item by item, why a server is or is not ready for a chosen client, and a re-run is comparable to earlier ones. Size: M–L.

##### 10.4 Remote host telemetry

Decided on 2026-11-12: LCC-to-LCC. The other approaches are kept below for context.

| Approach | How it works | Pros | Cons |
|---|---|---|---|
| LCC-to-LCC (chosen) | LCC on the target host serves its existing telemetry and evidence endpoints read-only, with a scoped key; the operator's LCC reads them as a remote provider | Reuses everything LCC already measures; no new agent | Needs LCC installed on each host |
| SSH collector (not chosen) | LCC runs fixed read-only commands over SSH through `ssh-agent`, reusing `JsonCommandTelemetryProvider` | Nothing to install remotely | SSH trust and key handling; fragile parsing |
| Collector service (not chosen) | A minimal separate telemetry daemon | Smallest footprint on the target | A second program to build, package, and secure |

- The remote LCC exposes a read-only scope: a separate key that can read telemetry, process, and evidence endpoints and cannot call any mutating route. This needs a key-scope concept in `services/security.py` (full key versus read-only key).
- The operator's LCC registers the remote LCC per runtime (URL plus read-only key), stored under the 7.3 rules, and implements a `RemoteLccTelemetryProvider` for `TelemetryManager`.
- Remote telemetry is always labeled with its source host and quality.
- Version handshake: the operator's LCC checks the remote LCC version and degrades cleanly when it is older.
- Prerequisites: step 7 complete, and the 7.1 access rules applied to every endpoint the remote LCC exposes.

Done when a remote target shows host telemetry that is clearly attributed to that host, or an honest unavailable state. Size: L.

Later, not in step 10: a multi-target dashboard showing several servers at once.

### Parallel Maintenance Lane

- Add persistent model-download progress and reconnectable job state for long Hugging Face pulls. Prefer Lemonade-owned `/v1/downloads` jobs (`stream=true`, `subscribe=false`) so progress survives page refreshes; do not move download ownership into LCC.
- Support Lemonade running as a systemd user unit (`systemctl --user`). Add a `LEMONADE_SYSTEMD_SCOPE=system|user` setting and pass `--user` to every `journalctl` and `systemctl` call (`routers/logs.py`, `services/process.py`, `services/metrics/task_history.py`, diagnostics collectors). Restarting a user unit needs no sudoers rule. LCC should do this itself rather than rely on PATH shims.

These tasks should be handled when relevant but should not interrupt the execution order without a concrete compatibility or safety issue:

- manually review official Lemonade Web UI/App changes and update the overlap matrix;
- add dated compatibility fixtures when Lemonade changes `/v1/system-info` or completion streaming;
- update [Tested Environment](./tested-environment.md) only after real smoke testing; a full Lemonade 11.x smoke pass is pending, since the 11.x compatibility fixes were merged without one;
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
- Access control: `backend/app/middleware/access_control.py`, `backend/app/services/security.py`, WebSocket routes in `backend/app/routers/logs.py` and `backend/app/routers/metrics.py`
- Local config persistence: `backend/app/services/setup.py`
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
- user-defined prompt and suite library
- backend-owned runs with progress, cancel, and presets
- full prompt/output preservation
- manual quality scores and notes
- resource correlation
- profile comparison
- diagnostic/report export

The ordered implementation is step 9 (Bench Lab v2) in the Current Execution Plan.

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
