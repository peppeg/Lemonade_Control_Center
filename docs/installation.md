# Installation

Lemonade Control Center is currently developed as two local services:

- FastAPI backend on `127.0.0.1:8000`
- SvelteKit frontend on `127.0.0.1:5173`

The intended production direction is a single local service that serves both the API and the built frontend. Until that packaging step is complete, use the development setup below.

## Prerequisites

- Linux
- Python 3.11 or newer
- Node.js 20 or newer
- a running Lemonade server

## Backend

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

## Frontend

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

Do not expose LCC directly to the public internet.
