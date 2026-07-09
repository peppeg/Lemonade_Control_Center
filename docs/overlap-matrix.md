# Overlap Matrix

Lemonade Control Center is an independent, unofficial companion for Lemonade. It intentionally overlaps with some Lemonade capabilities where a guided operator console needs basic runtime, model, and configuration visibility.

The goal is not to replace official Lemonade tools. The goal is to make Lemonade easier to operate, verify, diagnose, and compare in local workstation workflows.

P0 audit and closeout notes are summarized in [P0 Closeout](./p0-closeout.md).

## Public Position

| Official surface | How LCC treats overlap |
|---|---|
| Lemonade CLI | Good overlap when LCC turns terminal operations into guided, repeatable graphical workflows. |
| Official Web UI/App | Higher-risk overlap. LCC should proceed only when it adds diagnostics, host context, workflow memory, or run evidence. |
| Lemonade API | Expected overlap. LCC should use Lemonade as the source of truth instead of reimplementing server behavior. |

## Decision Rules

| Situation | LCC decision rule |
|---|---|
| Feature is mainly CLI-driven | Make it safer, visible, and repeatable through the GUI. |
| Feature is already strong in the official Web UI/App | Add a clear operator-console differentiator or avoid it. |
| Feature is API-level | Use the API and focus on orchestration, UX, and diagnostics. |
| Feature is weak or absent in official surfaces | Invest only if it supports the operator-console identity. |

## Matrix

| Area | Official Lemonade coverage | LCC role | Decision |
|---|---|---|---|
| Chat | Covered by official tools and API-compatible clients | LCC should not become a chat client | Avoid |
| Server health/status | CLI, Web UI/App, API | Show status beside host, process, and diagnostic context | Keep |
| Logs | CLI/Web UI/App/log APIs | Parse, classify, and correlate with runtime state | Differentiate |
| Model inventory | CLI/Web UI/App/API | Compact operational inventory, loaded state, canonical names | Keep compact |
| Catalog/download | CLI/Web UI/App/API | Support guided setup and profile workflows, not marketplace browsing | Keep minimal |
| Hugging Face intake | Official pull/import support exists | Add compatibility checks, quant choice, memory estimate, profile, smoke test | P1 candidate |
| Load/unload | CLI/Web UI/App/API | Guided load plan, saved options, risk estimate, process evidence | Differentiate |
| Backend selection | CLI/config/API | Show requested backend and observed runtime/backend when possible | Keep guided |
| Runtime config | CLI/Web UI/App/API | Keep minimal; separate Lemonade-owned config from LCC preferences | Keep minimal |
| Profiles/saved intent | Lemonade has recipe options; human workflow intent is broader | Store why a setup exists and how it performed | Invest |
| Benchmarks | Lemonade has benchmark tooling | Focus on workflow outputs, resource context, notes, and evidence | Differentiate strongly |
| Run Evidence | Partially covered by benchmark outputs/logs | Save prompt, output, model/profile/options, metrics, logs, RAM/swap, and process evidence in one request window | P1 core |
| Long-term telemetry | Better handled by telemetry/observability stacks | Keep short operator windows; avoid becoming a Grafana clone | Keep modest |
| System/process context | Limited or outside Lemonade | PID, cmdline, memory, swap, systemd, journal, disk, hardware context | Invest |
| Diagnostic bundle | Not a single official operator bundle | Sanitized support snapshot for issues and debugging | P0 |
| Privacy/sanitization | Project-specific need | Redact keys, tokens, paths, hostnames, LAN details where appropriate | P0 |
| Server discovery | Lemonade supports scan/beacons | Guided discovery, URL normalization, local-vs-remote explanation | P0 |
| Multi-host awareness | Possible through API targets | Keep modest; focus on Connection Doctor and trusted targets | P1 candidate |
| Docker deployment | Separate packaging/deployment concern | Provide a clear deployment path and document host-telemetry limits | P1 candidate |

## Strong LCC Differentiators

- Guided graphical workflows for users who do not want to operate Lemonade primarily through commands.
- Local machine awareness: process, PID, command line, RAM, swap, disk, systemd, and journal context.
- Operator preflight before risky load actions.
- Post-load verification of what actually happened.
- Diagnostic bundles suitable for support and GitHub issues.
- Workflow profiles that capture intent, not just backend flags.
- Run Evidence for comparing model/profile behavior in real tasks.
- Optional hardware telemetry providers such as AMD-focused tooling where available.

## Areas To Avoid As Product Identity

- Chat UI.
- Alternative model marketplace.
- Raw clone of official logs/config pages.
- Long-term generic telemetry dashboards.
- Broad backend installer UX before readiness checks are mature.

## Current P0 Focus

1. Keep public positioning clear: LCC is an unofficial guided operator console.
2. Improve Connection Doctor and server discovery.
3. Strengthen guided model operations.
4. Review diagnostic bundle content and sanitization.
5. Audit the official Web UI/App manually before investing in high-overlap areas.
