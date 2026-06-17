# Development

This project uses a FastAPI backend and a SvelteKit frontend.

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

Linux host inspection depends on what the machine exposes through `/proc`, `/sys`, `systemctl`, `journalctl`, `psutil`, and available sensor tooling. Missing probes should degrade gracefully.

## Local Data

Runtime data is stored under backend-managed data paths and is intentionally excluded from git. Do not commit secrets, local settings, diagnostic bundles, or private planning documents.
