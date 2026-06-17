#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON_BIN="${PYTHON:-python3}"

usage() {
  cat <<'EOF'
Lemonade Control Center installer

Usage:
  ./install.sh

Environment overrides:
  PYTHON=python3.12 ./install.sh

What it does:
  - checks Python, Node.js, and npm
  - creates backend/.venv when missing
  - installs backend requirements
  - installs frontend dependencies
  - builds the static frontend
  - creates backend/.env from .env.example when missing

It does not configure systemd, firewall rules, LAN mode, or Lemonade itself.
EOF
}

log() {
  printf '\n==> %s\n' "$1"
}

die() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python not found. Install Python 3.11+ or set PYTHON=/path/to/python."
command -v node >/dev/null 2>&1 || die "Node.js not found. Install Node.js 20+."
command -v npm >/dev/null 2>&1 || die "npm not found. Install npm with Node.js."

"$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required.")
PY

node -e "const major = Number(process.versions.node.split('.')[0]); if (major < 20) { process.exit(1); }" \
  || die "Node.js 20+ is required."

log "Creating backend virtual environment"
if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  "$PYTHON_BIN" -m venv "$BACKEND_DIR/.venv"
else
  printf 'backend/.venv already exists; reusing it.\n'
fi

log "Installing backend dependencies"
"$BACKEND_DIR/.venv/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"

log "Preparing backend environment file"
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$BACKEND_DIR/.env"
  printf 'Created backend/.env from .env.example.\n'
else
  printf 'backend/.env already exists; leaving it unchanged.\n'
fi

log "Installing frontend dependencies"
npm --prefix "$FRONTEND_DIR" install

log "Building frontend"
npm --prefix "$FRONTEND_DIR" run build

cat <<EOF

Lemonade Control Center is installed.

Start the unified runtime:

  cd "$BACKEND_DIR"
  source .venv/bin/activate
  python -m app.run

Open:

  http://127.0.0.1:17600

Optional trusted-LAN mode:

  cd "$BACKEND_DIR"
  source .venv/bin/activate
  APP_HOST=0.0.0.0 APP_PORT=4242 REQUIRE_AUTH=true LAN_MODE=true python -m app.run

Before using LAN mode, set LCC_API_KEY in backend/.env.
EOF
