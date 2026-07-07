#!/usr/bin/env bash
# Launch the Regime Terminal web app. Run:  bash run.sh   (or ./run.sh)
cd "$(dirname "$0")" || exit 1
echo "Regime Terminal -> http://localhost:8000  (Ctrl-C to stop)"
( sleep 1; command -v open >/dev/null && open http://localhost:8000 || \
  command -v xdg-open >/dev/null && xdg-open http://localhost:8000 ) >/dev/null 2>&1 &
exec python3 serve.py
