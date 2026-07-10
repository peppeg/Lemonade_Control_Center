# Development

This project uses a FastAPI backend and a SvelteKit frontend.

Development runs them as two separate processes for hot reload. The normal local runtime can use a single FastAPI process after `npm run build`.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful check:

```bash
python -m compileall -q app
```

## Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Useful checks:

```bash
npm run check
npm run build
```

## Runtime Assumptions

During development, Vite proxies `/api` requests to FastAPI. Lemonade is expected to be reachable at the configured `LEMONADE_URL`, which defaults to `http://localhost:13305`.

## Unified Runtime Smoke Test

After changing frontend build or backend static serving behavior:

```bash
cd frontend
npm run build
```

```bash
cd backend
source .venv/bin/activate
python -m app.run
```

Then verify:

```text
http://127.0.0.1:17600/
http://127.0.0.1:17600/dashboard
http://127.0.0.1:17600/models
http://127.0.0.1:17600/api/health
```

Direct browser refresh on frontend routes should return the dashboard shell, not a backend 404.

Linux host inspection depends on what the machine exposes through `/proc`, `/sys`, `systemctl`, `journalctl`, `psutil`, and available sensor tooling. Missing probes should degrade gracefully.

## Backend Readiness Manual Check

After changing backend readiness collection or presentation, verify:

- Dashboard shows a loading state before readiness data arrives.
- An unreachable Lemonade target produces an unavailable warning, not zero-valued success data.
- Installed, update-required, installable, unsupported, and unknown states have correct counts.
- A response with no backend entries is described as empty.
- Search and state filters work on the Backends page.
- Operator actions can be copied, and provided release links open separately.
- Desktop and mobile navigation reach the Backends page.
- A diagnostic bundle contains `backend_readiness.json` even when Lemonade is unavailable.

## Workflow Defaults Manual Check

- Saving LCC Workflow Defaults survives a page reload.
- Existing `lcc.requestDefaults` browser data migrates to `lcc.workflowDefaults` without losing values.
- Applying a model profile updates the workflow defaults and preserves the profile name.
- Smoke Test uses the saved token, temperature, timeout, and stop settings within its safety limits.
- New smoke-test Run Evidence records contain the request settings used.
- Bench Lab quick tests initialize token and temperature controls from the same defaults.

## Completion Runner Checks

Smoke Test and Bench Lab share the core completion transport, but Smoke Test must not depend on the optional Bench router or storage.

- Metadata-only chunks and `delta.content: null` do not fail the stream.
- Reasoning content is kept separate from final assistant text.
- Primary endpoint failure falls back from `/api/v1/chat/completions` to `/v1/chat/completions`.
- HTTP, connection, timeout, protocol, and empty-response failures are returned as structured error kinds.
- Interrupted streams retain partial output and close the response.
- Run Evidence reports the completion endpoint and whether token counts came from the API or an estimate.
- The runner uses the active Lemonade runtime configured in Settings.

## Run Evidence Manual Check

- Smoke tests and load attempts appear under Run Evidence with the newest record first.
- Kind, result, and text filters keep the selected detail consistent with the visible list.
- Smoke-test detail shows request settings, prompt, response, separate reasoning, metrics, and runtime evidence.
- Load-attempt detail shows requested and observed load state without completion-only fields.
- JSON and Markdown downloads contain the selected complete record and use a safe attachment filename.

## Local Data

Runtime data is stored under backend-managed data paths and is intentionally excluded from git. Do not commit secrets, local settings, diagnostic bundles, or private planning documents.
