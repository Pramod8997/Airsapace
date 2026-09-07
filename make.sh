#!/usr/bin/env bash
# AirStat India — one-command pipeline: generate replay data → seed → calculate index →
# backtest → start API → start dashboard. Safe to re-run; idempotent where possible.
#
# Usage:
#   ./make.sh            full pipeline (regenerates replay data if missing, fresh seed, starts servers)
#   ./make.sh --keep     re-seed without dropping tables (keeps existing data)
#   ./make.sh --serve    skip pipeline, just start both servers
#   ./make.sh --stop     stop any AirStat servers started by this script
#   ./make.sh --test     run backend tests only
#   ./make.sh --fresh-data  force regeneration of the replay dataset
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
VENV=".venv"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-5173}"
API_PID=""
UI_PID=""
RUN_DIR="/tmp/airstat"
mkdir -p "$RUN_DIR"

log()  { printf '\033[1;34m[make]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[make]\033[0m %s\n' "$*" >&2; }

stop_existing() {
  for pidfile in "$RUN_DIR/api.pid" "$RUN_DIR/ui.pid"; do
    if [[ -f "$pidfile" ]]; then
      pid=$(cat "$pidfile")
      if kill "$pid" 2>/dev/null; then log "stopped $pidfile pid=$pid"; fi
      rm -f "$pidfile"
    fi
  done
  # also catch anything still bound to the ports (previous manual runs)
  for port in "$API_PORT" "$UI_PORT"; do
    pid=$(ss -tlnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | grep -oP 'pid=\K[0-9]+' | head -1)
    [[ -n "$pid" ]] && { kill "$pid" 2>/dev/null && log "killed process on port $port (pid $pid)"; } || true
  done
}

start_api() {
  log "starting API on :$API_PORT"
  nohup "$PY" -m uvicorn backend.app.main:app --port "$API_PORT" >"$RUN_DIR/api.log" 2>&1 &
  API_PID=$!
  echo "$API_PID" > "$RUN_DIR/api.pid"
  for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1 && { log "API healthy (pid $API_PID)"; return 0; }
    sleep 1
  done
  warn "API failed to become healthy — check $RUN_DIR/api.log"; return 1
}

start_ui() {
  if [[ ! -d frontend/node_modules ]]; then
    log "installing frontend dependencies (first run)"
    (cd frontend && npm install)
  fi
  log "starting dashboard on :$UI_PORT"
  (cd frontend && nohup npm run dev -- --port "$UI_PORT" >"$RUN_DIR/ui.log" 2>&1 & echo $! >"$RUN_DIR/ui.pid")
  for _ in $(seq 1 30); do
    curl -sf "http://localhost:$UI_PORT/" >/dev/null 2>&1 && { log "dashboard healthy (pid $(cat "$RUN_DIR/ui.pid"))"; return 0; }
    sleep 1
  done
  warn "dashboard failed to start — check $RUN_DIR/ui.log"; return 1
}

trap '[[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true' EXIT

case "${1:-build}" in
  --stop)
    stop_existing
    exit 0
    ;;

  --test)
    "$PY" -m pytest backend/tests -q
    exit 0
    ;;

  --serve)
    stop_existing || true
    start_api
    start_ui
    log "dashboard: http://localhost:$UI_PORT  ·  API: http://127.0.0.1:$API_PORT/health"
    log "logs in $RUN_DIR/{api,ui}.log — stop with ./make.sh --stop"
    wait
    ;;

  *)
    MODE="${1:-}"

    # 1. environment
    if [[ ! -x "$PY" ]]; then
      log "creating Python venv"
      python3 -m venv "$VENV"
      "$PY" -m pip install --quiet -r requirements.txt
    fi

    # 2. replay dataset (generate if missing or forced)
    if [[ "$MODE" == "--fresh-data" || ! -f data/fixtures/replay_quotes.jsonl ]]; then
      log "generating replay dataset (seed 26056)"
      [[ "$MODE" == "--fresh-data" ]] && rm -f data/fixtures/replay_quotes.jsonl
      "$PY" scripts/generate_replay_data.py
    else
      log "replay dataset present — skipping generation (use --fresh-data to force)"
    fi

    # 3. seed + index + backtest
    log "seeding database and running pipeline"
    "$PY" scripts/seed.py

    # 4. tests
    log "running backend tests"
    "$PY" -m pytest backend/tests -q

    # 5. servers
    stop_existing || true
    start_api
    start_ui
    log "pipeline complete"
    log "dashboard: http://localhost:$UI_PORT  ·  API: http://127.0.0.1:$API_PORT/health"
    log "logs in $RUN_DIR/{api,ui}.log — stop with ./make.sh --stop"
    wait
    ;;
esac
