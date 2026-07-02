#!/usr/bin/env bash
# ============================================================
#   Pacific Web Builder - one-click launcher (macOS / Linux / Git Bash)
#   Run:  bash start.sh   (from inside the bcbuiswebbuildertool folder)
#   Creates .env if missing, starts the server, opens an HTTP/2 tunnel.
# ============================================================
set -e
cd "$(dirname "$0")"

PORT="${PORT:-5000}"

echo "============================================================"
echo "   PACIFIC WEB BUILDER - Launcher"
echo "============================================================"

# 1) Ensure a .env exists so login works (does NOT overwrite yours)
if [ ! -f .env ]; then
  echo "Creating .env with default password: careful2026"
  echo "ADMIN_PASSWORD=careful2026" > .env
else
  echo "Found existing .env - using your settings."
fi

# 2) Start the server in the background
echo "Starting server on http://localhost:$PORT ..."
python src/server.py &
SERVER_PID=$!

# Stop the server if this script is interrupted
trap 'echo; echo "Stopping..."; kill $SERVER_PID 2>/dev/null; exit 0' INT TERM

# 3) Wait, then start the tunnel on HTTP/2 (foreground so you see the URL)
sleep 6
if command -v cloudflared >/dev/null 2>&1; then
  if [ -n "$TUNNEL_NAME" ]; then
    echo "Starting NAMED tunnel '$TUNNEL_NAME' — your permanent URL..."
    cloudflared tunnel run --url "http://localhost:$PORT" "$TUNNEL_NAME"
  else
    echo "Starting public HTTPS tunnel (HTTP/2)... (URL changes each restart —"
    echo "see 'Stable public URL' in the README for a permanent one)"
    cloudflared tunnel --url "http://localhost:$PORT" --protocol http2
  fi
else
  echo "cloudflared not installed - running LOCAL ONLY at http://localhost:$PORT"
  wait $SERVER_PID
fi
