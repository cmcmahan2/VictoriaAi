#!/usr/bin/env bash
# One-command launch: creates a venv, installs deps, starts the app,
# and opens http://localhost:8787 in your browser.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo "[slipstream] creating virtualenv..."
  "$PY" -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[slipstream] WARNING: ANTHROPIC_API_KEY is not set — screenshot parsing will be disabled."
fi

exec uvicorn main:app --port "${SLIPSTREAM_PORT:-8787}"
