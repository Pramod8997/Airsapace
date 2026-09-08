#!/usr/bin/env bash
# AirStat India — one-command pipeline: generate replay data → seed → calculate index →
# backtest → start API → start dashboard. Safe to re-run; idempotent where possible.
#
# Usage:
#   ./make.sh            full pipeline (regenerates replay data if missing, fresh seed, starts servers)
#   ./make.sh --keep     re-seed without dropping tables (keeps existing data)
#   ./make.sh --serve    skip pipeline, just start both servers
#   ./make.sh --demo     FULL EXPERIENCE: pipeline + servers + sim portal + 1s collector loop
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
PORTAL_PID=""
COLLECTOR_PID=""
RUN_DIR="/tmp/airstat"
LOCK="$RUN_DIR/pipeline.lock"
mkdir -p "$RUN_DIR"

log()  { printf '\033[1;34m[make]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[make]\033[0m %s\n' "$*" >&2; }

# pipeline lock — seed.py drop_all + SQLite cannot tolerate concurrent runs
if [[ -e "$LOCK" ]] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then
  warn "another make.sh is running (pid $(cat "$LOCK")) — refusing to start. Stop it with ./make.sh --stop (kills its servers too) or kill $(cat "$LOCK")."
  exit 1
fi
echo $$ > "$LOCK"

stop_existing() {
  for pidfile in "$RUN_DIR/api.pid" "$RUN_DIR/ui.pid" "$RUN_DIR/portal.pid" "$RUN_DIR/collector.pid"; do
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

start_portal() {
  log "starting sim fare portal on :8811 (robots.txt-gated scrape target)"
  nohup "$PY" scripts/serve_sim_portal.py >"$RUN_DIR/portal.log" 2>&1 &
  PORTAL_PID=$!
  echo "$PORTAL_PID" > "$RUN_DIR/portal.pid"
  for _ in $(seq 1 20); do
    curl -sf "http://127.0.0.1:8811/robots.txt" >/dev/null 2>&1 && { log "portal healthy (pid $PORTAL_PID)"; return 0; }
    sleep 1
  done
  warn "portal failed to start — check $RUN_DIR/portal.log"; return 1
}

start_collector() {
  local interval="${1:-1}"
  log "starting collector loop: fresh collection every ${interval}s (DB auto-pruned to 90 virtual days)"
  nohup "$PY" scripts/collect_demo.py --interval "$interval" >"$RUN_DIR/collector.log" 2>&1 &
  COLLECTOR_PID=$!
  echo "$COLLECTOR_PID" > "$RUN_DIR/collector.pid"
  log "collector running (pid $COLLECTOR_PID) — dashboard auto-refreshes every 10s"
}

cleanup() {
  rm -f "$LOCK"
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "$PORTAL_PID" ]] && kill "$PORTAL_PID" 2>/dev/null || true
  [[ -n "$COLLECTOR_PID" ]] && kill "$COLLECTOR_PID" 2>/dev/null || true
}
trap cleanup EXIT

ARG="${1:-}"

case "$ARG" in
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
    MODE="$ARG"

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

    # 6. demo mode: portal + collector loop
    if [[ "$MODE" == "--demo" ]]; then
      start_portal || warn "continuing without portal (sim sources still cycle)"
      start_collector 1
    fi
    log "pipeline complete"
    log "dashboard: http://localhost:$UI_PORT  ·  API: http://127.0.0.1:$API_PORT/health"
    log "logs in $RUN_DIR/{api,ui,portal,collector}.log — stop with ./make.sh --stop"
    wait
    ;;
esac
