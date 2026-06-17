# Contributing to Lemonade Control Center

Thanks for taking the time to look at Lemonade Control Center.

LCC is an operator console for a local Lemonade runtime. It is not a chat UI, a model hub replacement, or a generic server administration panel. Changes should keep that scope clear: make local inference operations easier to understand, safer to repeat, and easier to diagnose.

## Project Principles

- Keep Lemonade-owned state and LCC-owned preferences visibly separate.
- Prefer explicit controls over hidden automation for operations that affect memory, model loading, services, or host state.
- Treat destructive and privileged actions as guarded operations.
- Keep Linux host inspection best-effort. Different machines expose sensors, systemd, journal logs, and GPU data differently.
- Avoid committing local secrets, private plans, captured personal logs, or machine-specific data.

## Local Development

Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

## Checks Before Submitting

Run the backend syntax check:

```bash
cd backend
python -m compileall -q app
```

Run the frontend checks:

```bash
cd frontend
npm run check
npm run build
```

## Security and Local Data

Do not commit:

- `.env` files
- `.private/`
- backend runtime data under `backend/app/data/`
- local logs, screenshots containing private host information, or generated diagnostic bundles
- API keys or Lemonade admin keys

LCC trusts localhost by default. LAN or remote access requires `LCC_API_KEY`; `REQUIRE_AUTH=true` can force the same key requirement for localhost.

## Pull Request Guidance

- Keep changes small and easy to review.
- Explain the operational behavior being changed.
- Include screenshots for UI changes when possible.
- Mention any Lemonade version or host capability assumptions.
- Avoid broad refactors unless they are required by the feature or bug fix.
