# AirStat India — SIH 2026 Build Documentation

Files:
- `CLAUDE.md` — operating contract for Claude Code / AI coding agents. Auto-loaded every session — read this first, it points to everything else.
- `PRD.md` — complete product requirements and acceptance criteria.
- `TRD.md` — technical architecture, stack, APIs, database and engineering requirements (canonical source for stack/schema/formula).
- `UI_UX_DESIGN.md` — unique Airspace Observatory UI/UX specification.
- `SECURITY.md` — webapp, API, collector, database and statistical-integrity security.
- `memory.md` — persistent current-state record (frozen decisions, sprint, blockers) for the team/AI coding assistants. Points to TRD/PRD for reference material rather than duplicating it.
- `log.md` — chronological development log; owns the per-session entry template.

## Quick start (one command)

```bash
./make.sh          # Linux/macOS — full pipeline + servers
make.bat           # Windows — same
```

Runs: venv/deps if missing → replay dataset (if missing) → seed (ingest → clean → index → backtest) → tests → API (:8000) → dashboard (http://localhost:5173). Idempotent; safe to re-run.

```bash
./make.sh --serve        # just start both servers (skip pipeline)
./make.sh --stop         # stop servers started by make.sh
./make.sh --test         # backend tests only
./make.sh --fresh-data   # regenerate the replay dataset first
./make.sh --keep         # re-seed without dropping tables
```

Logs land in `/tmp/airstat/` (Linux) / `%TEMP%\airstat` (Windows). Ports via `API_PORT` / `UI_PORT` env vars.

## Quick start (manual, step by step)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. deterministic replay dataset (data/fixtures/replay_quotes.jsonl)
.venv/bin/python scripts/generate_replay_data.py

# 2. seed DB (SQLite at data/airstat.db by default; DATABASE_URL for PostgreSQL), run pipeline + index + backtest
.venv/bin/python scripts/seed.py

# 3. serve the API (Swagger UI at /docs)
.venv/bin/uvicorn backend.app.main:app --reload

# 4. tests
.venv/bin/python -m pytest backend/tests -q
```

Key endpoints: `/api/v1/index/latest`, `/api/v1/index/history`, `/api/v1/fares`,
`/api/v1/quality`, `/api/v1/methodology`, `/api/v1/backtests`, `/health`.
The dashboard must not depend on live scraping — the seeded replay dataset is the
demo data source (REPLAY mode).

## Repo layout

`backend/` (FastAPI app, models, pipeline services, tests) ·
`frontend/` (React + TypeScript + Vite dashboard, Airspace Observatory) ·
`statistical_engine/` (pure deterministic index/outlier/quality/backtest logic) ·
`collectors/` (source-adapter contract) ·
`scripts/` (replay generator, seed) ·
`data/fixtures/` (generated replay dataset — regenerable, do not hand-edit).

## Recommended reading order

**For an AI coding agent:** `CLAUDE.md` first (always) — it tells you which of the files below to open for a given task, rather than reading all of them every session.

**For a human reviewer, front to back:**
1. PRD.md
2. TRD.md
3. SECURITY.md
4. UI_UX_DESIGN.md
5. memory.md
6. log.md

## Source note

The supplied SIH PPTX was reviewed. It contains headings for Technical Approach / Methodology / Architecture / Tech Stack but does not provide a populated technology stack, so the TRD explicitly labels its stack as the recommended implementation stack.
