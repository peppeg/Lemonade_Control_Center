# Roadmap

Lemonade Control Center is a guided graphical operator console for Lemonade. It is not a chat UI and it is not a replacement for official Lemonade tools.

The roadmap is organized around one rule:

```text
Make Lemonade easier to operate, then make the runtime behavior easier to prove.
```

## P0: Direction And Operator Basics

P0 is about making the product direction concrete and removing ambiguity around overlap with official Lemonade tooling.

Recommended order:

1. Positioning and overlap discipline.
2. Connection Doctor.
3. Guided Load v2.
4. Diagnostic Bundle and sanitization review.
5. Manual official Web UI/App audit.

### Positioning

Status: in progress

- Describe LCC as a guided operator console.
- Keep the "not a chat interface" boundary.
- Be explicit that official Lemonade UI/CLI are capable and remain the baseline.
- Document where LCC overlaps and where it must differentiate.

### Overlap Matrix

Status: started

- Track Lemonade UI/CLI coverage.
- Track LCC coverage.
- Decide keep, cut, or differentiate.
- Use the matrix to prevent lazy duplication.

### Connection Doctor

Status: V0 implemented, needs UI polish and deeper runtime evidence

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

Next:

- Add a one-click smoke test after a healthy connection.
- Show process command line and observed backend when a model is loaded.
- Promote trusted/manual server selection from setup discovery into the settings workflow.

### Guided Load V2

Status: in progress, first smoke-test evidence hook implemented

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
- Show backend requested vs backend observed after load when possible. V0 post-load notification includes observed backend/context/PID when process evidence is available.
- Show RAM/swap risk before and after load. V0 estimates planning headroom and context risk from hardware/process/model size data.
- Offer a small smoke test, not a chat UI. V0 is implemented from the active model panel.
- Save first evidence hooks for future Run Evidence. V0 stores smoke-test evidence locally.

Next:

- Store the load attempt summary as a first Run Evidence seed.
- Surface observed command line/backend details directly in the load result panel instead of only in notification/system view.

### Diagnostics Bundle V1

Status: V1 sanitization pass implemented, needs real-world bundle review

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

Status: V1 implemented, needs manual archive review before public sharing

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

Status: pending

Goal:

```text
Verify what the official Web UI/App actually covers so LCC does not invest in weak duplication.
```

Audit targets:

- pin/unpin UX
- backend install/uninstall UX
- config editing depth
- log filtering/parsing depth
- benchmark UI coverage
- system stats/storage UI coverage
- Hugging Face variant/update UX
- cloud provider UX

### Compatibility Discipline

Status: started

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

Profiles should connect model, target server, load options, request defaults, notes, known caveats, and last useful result.

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

Status: seed implemented for post-load smoke tests

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
- relevant logs in the run window
- JSON/Markdown export

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
