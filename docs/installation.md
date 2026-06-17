# Installation

Lemonade Control Center can run in two modes:

- unified runtime: one FastAPI process serves both `/api/*` and the built dashboard
- development mode: FastAPI and Vite run as two separate processes

The unified runtime is the recommended mode for normal local use.

## Prerequisites

- Linux
- Python 3.11 or newer
- Node.js 20 or newer
- a running Lemonade server

## Unified Runtime

Build the frontend:

```bash
cd frontend
npm install
npm run build
```

Start LCC:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python -m app.run
```

Open:

```text
http://127.0.0.1:17600
```

The default runtime port is `17600`.

## Development Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health check:

```bash
curl http://127.0.0.1:8000/api/health
```

## Development Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

## Local Network Access

The safest default is localhost-only access. To use LCC from another machine on the same trusted LAN, configure the backend to bind to the LAN interface or `0.0.0.0`, set `LCC_API_KEY`, and keep host firewall rules explicit.

Example:

```bash
cd backend
APP_HOST=0.0.0.0 APP_PORT=4242 REQUIRE_AUTH=true LAN_MODE=true python -m app.run
```

Do not expose LCC directly to the public internet.
