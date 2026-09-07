# AirStat India --- Development Log

**Purpose:** Chronological record of project execution.

------------------------------------------------------------------------

## Status Legend

-   `TODO`
-   `IN PROGRESS`
-   `BLOCKED`
-   `DONE`
-   `DEFERRED`

------------------------------------------------------------------------

# 2026-09-07 --- Project Documentation Baseline

**Status:** DONE

### Completed

-   [x] Analyzed SIH Problem Statement 26056.
-   [x] Defined AirStat India product direction.
-   [x] Created build-ready PRD.
-   [x] Created Technical Requirements Document.
-   [x] Created unique UI/UX design specification.
-   [x] Created security requirements.
-   [x] Created persistent project memory file.
-   [x] Created development log.

### Important source observation

The supplied PPTX contains sections/headings for Technical Approach,
Methodologies, Architecture and Tech Stack, but those fields are not
populated with an actual technology stack. Therefore the TRD defines a
recommended implementation stack rather than attributing that stack to
the PPTX.

### Next

-   [ ] Freeze team roles.
-   [ ] Create repository.
-   [ ] Initialize Docker Compose.
-   [ ] Initialize PostgreSQL.
-   [ ] Implement database migrations.
-   [ ] Implement canonical fare schema.
-   [ ] Build index-engine unit tests before live collectors.
-   [ ] Build replay dataset.
-   [ ] Implement first source adapter.
-   [ ] Implement FastAPI skeleton.
-   [ ] Implement dashboard shell.

------------------------------------------------------------------------

# 2026-09-08 --- Agent Plugin Setup

**Status:** DONE

### Objective

-   Set up the three agent plugins/skills specified in `prompt.md` and record the outcome.

### Work Completed

-   [x] Verified all three source repos reachable (`DietrichGebert/ponytail`, `Graphify-Labs/graphify`, `nextlevelbuilder/ui-ux-pro-max-skill`).
-   [x] Verified `graphify` already installed (CLI v0.8.35 at `~/.local/bin/graphify`, skill registered at `~/.claude/skills/graphify/`) — no install needed.
-   [x] Installed `ponytail` v4.9.0 plugin (user scope): marketplace add → pre-install inspection → install.
-   [x] Installed `ui-ux-pro-max` v2.13.0 plugin (user scope): marketplace add → pre-install inspection → install.
-   [x] Created `.claudeignore` with `graphify-out/` and `graph.json` entries (graph regeneration must not invalidate agent prompt cache).
-   [x] Confirmed ui-ux-pro-max usage mode with the team: design generation allowed, but only from the Airspace Observatory brief.
-   [ ] Deferred by choice: `/graphify .` knowledge-graph build (run when first needed).

### Technical Changes

-   None to product code — agent tooling only.

### Files Changed

``` text
- .claudeignore (new)
- memory.md (Frozen Decisions → Agent Tooling; Decisions Log +2 rows)
```

### Tests

``` text
Command: git ls-remote <3 repos>; graphify --version; claude plugin list
Result: all 3 repos reachable; graphify 0.8.35; ponytail@ponytail 4.9.0 and ui-ux-pro-max@ui-ux-pro-max-skill 2.13.0 both enabled.
```

### Data/Statistical Changes

-   None.

### Security Changes

-   Pre-install inspection of both plugin repos: manifests, file inventory, pattern scan for exfiltration / exec / credential access — clean.
-   ponytail registers lifecycle hooks (SessionStart / SubagentStart / UserPromptSubmit); its hook scripts verified local-only (config read/write + instruction injection, no network, no subprocess execution).

### UI/UX Changes

-   None (tooling decision recorded in `memory.md` §4 Agent Tooling).

### Decisions

-   ui-ux-pro-max may generate design only when fed the Airspace Observatory direction (`UI_UX_DESIGN.md`) as the brief — never a generic "airfare dashboard" prompt. Accessibility/UX-guideline checks unrestricted.

### Blockers

-   None.

### Next Steps

-   [ ] Restart Claude Code so the two new plugins activate in new sessions.
-   [ ] Run `/graphify .` when the knowledge graph is first needed.

### Notes

-   Plugins are user-scope on this machine, not committed to the repo; teammates must install separately (commands in `prompt.md`).

------------------------------------------------------------------------

# 2026-09-08 --- Backend Core: Canonical Model, Cleaning, Deterministic Index, Replay, Backtest, API

**Status:** DONE

### Objective

- Build the smallest correct system per CLAUDE.md §6 priority order: canonical data model → cleaning → deterministic index → 30-day replay/backtest → API.

### Work Completed

- [x] Full PRD §10 data model in SQLAlchemy (15 tables: registries, ScrapeJob, RawObservation, FareQuote, QualityAssessment, MethodologyVersion, IndexBasket/IndexWeight, CalculationRun, IndexValue, BacktestRun, User, AuditLog) with TRD §7 indexes and natural-key uniqueness.
- [x] Canonical contract (TRD §6) as Pydantic `FlightQuote` in `collectors/core/models.py` + `FlightSource` adapter ABC (TRD §5).
- [x] Pure deterministic statistical engine: Laspeyres index `I_t = [Σ(w_i×P_i,t/P_i,0)/Σw_i]×100` with all cuts (national/combined, national×lead, route/combined, route×lead), median spec aggregation, MAD outlier flagging (flag, never delete), versioned quality scoring (QS-v1), backtest metrics (MAE/RMSE/MAPE/correlation/trend-direction).
- [x] Ingest pipeline: job-key idempotency, immutable raw storage (duplicates keep raw rows; only the processed row is skipped), dedup by natural key, INVALID/SOLD_OUT/MISSING/REJECTED classification, quality-score persistence.
- [x] Index runner: CalculationRun with SHA-256 input fingerprint (SECURITY.md §16), immutable never-overwritten IndexValues, idempotent re-runs.
- [x] Deterministic replay dataset generator (seed 26056): 75 days × 10 routes × 5 lead times × 5 synthetic sources = 14,250 jobs / 36,469 quotes incl. sold-out, source outage, failures, duplicates, schema violations, fare-arithmetic errors, fat-finger outliers.
- [x] Seed script: registries, methodology APIX-v1.0, basket BASKET-2026.09 (50 route×lead weights), full pipeline, synthetic reference + 45-point backtest.
- [x] FastAPI: all 10 FR-16 endpoints + /health + /fares.csv export; security headers, per-IP token-bucket rate limit, pagination caps, input validation, CORS allowlist (empty=same-origin).
- [x] 42 tests passing (unit: formula/determinism/reweighting/outliers/quality/backtest; integration: ingest→clean→index; API via TestClient; rate-limit middleware).

### Technical Changes

- New packages: `backend/app` (config, db, models, schemas, api, middleware, services), `statistical_engine/`, `collectors/core/`, `scripts/`, `backend/tests/`.
- Python 3.10 venv (machine max is 3.11 without ensurepip; TRD targets 3.12+ — code is 3.10+ compatible, no 3.12-only features).
- Dev DB defaults to SQLite (`data/airstat.db`) because the local Docker daemon is off; `DATABASE_URL` switches to PostgreSQL unchanged (portable types: JSON, String enums; no PG-specific SQL).

### Files Changed

``` text
- requirements.txt, .gitignore, README.md (new/updated)
- collectors/__init__.py, collectors/core/{__init__,models,base_source}.py (new)
- statistical_engine/{__init__,normalization,outliers,quality,aggregation,basket,index,backtest}.py (new)
- backend/app/{__init__,config,db,models,schemas,api,middleware,main}.py, backend/app/services/{__init__,pipeline,index_runner}.py (new)
- scripts/{generate_replay_data,seed}.py (new); data/fixtures/replay_quotes.jsonl (generated)
- backend/tests/{conftest,test_engine,test_pipeline,test_api}.py (new)
```

### Tests

``` text
Command: .venv/bin/python -m pytest backend/tests -q
Result: 42 passed (4 deprecation warnings: FastAPI on_event, anyio alias)
E2E: generate → seed (14,250 jobs; 36,401 stored; 35 dup; 95 invalid; 1,622 sold-out; 641 outliers flagged) → serve → curl /health, /index/latest, /index/history (DAILY/WEEKLY, lead/route filters), /fares (+filters/pagination), /fares.csv, /routes, /airlines, /sources, /quality, /methodology, /backtests, 404/422 paths, security headers — all correct.
```

### Data/Statistical Changes

- Methodology APIX-v1.0 published: Laspeyres, base period 2026-06-25→2026-07-24 (=100), median consumer-payable spec prices (base+taxes+mandatory; convenience fee excluded per FR-09), missing specs reweighted (no imputation, imputation_rate reported 0), outliers flagged not deleted.
- Basket: 10 PRD §14 routes × 5 lead times, placeholder weights (route × lead distribution, both sum to 1) — **placeholder, production weights must derive from DGCA traffic data** (open question).
- Backtest vs synthetic reference (labeled "synthetic-reference-demo (not DGCA)"): MAE 0.99, RMSE 1.21, MAPE 0.97%, corr 0.96, trend-direction 0.95 over 45 points. Reference is derived from APIx + noise purely to demonstrate the workflow — honest labeling everywhere; real DGCA series pending.
- Replay window 2026-06-25→2026-09-07; Independence-Day travel spike (Aug 12–18) visible in weekly series — usable for shock-detection demo.

### Security Changes

- Security headers middleware (CSP default-src 'none', frame-ancestors 'none', nosniff, DENY, no-referrer; HSTS only in production env).
- Per-IP token-bucket rate limit (default 120/min, env-configurable), /health exempt.
- Input validation on every query param (IATA patterns, enum membership, page-size cap 500); SQLAlchemy parameterization only; CORS allowlist empty by default.
- Route/source registry checks at ingest (data-poisoning guard, SECURITY.md T8); raw payloads stored as data, never executed.
- Deferred (no write endpoints exist yet): JWT auth, RBAC, audit-log write path, Argon2id — lands with first authenticated/admin feature.

### UI/UX Changes

- None (backend session). API responses shaped for the Airspace Observatory dashboard (index/latest changes, lead-time series, quality meter inputs, source health).

### Decisions

- Dev DB = SQLite via DATABASE_URL default; PostgreSQL remains the production target (Docker daemon unavailable locally today). Not an architectural change — no PG-specific constructs used.
- Duplicates are defined by natural key (source+flight+cabin+class+instant), not price; raw rows are kept for duplicates, processed rows are not.
- `create_all` for the prototype; Alembic migrations deferred until schema stabilises.
- Stdlib `statistics` used instead of pandas/NumPy for this slice (medians, correlation); no heavy deps until a task needs them.
- Generator DOW amplitude damped (0.96–1.06) and event spike 1.15 after first seed showed ±9% daily lockstep weekday swings — same-lead specs move together because departure = t+L.

### Blockers

- None. (Machine lacks python3.12 and a running Docker daemon — worked around; noted above.)

### Next Steps

- [ ] React dashboard shell (UI_UX_DESIGN.md Airspace Observatory) consuming these endpoints.
- [ ] First real source adapters (Playwright/httpx) behind the FlightSource contract + APScheduler.
- [ ] Alembic migrations once schema is stable; Docker Compose when daemon is available.
- [ ] Auth (JWT + RBAC roles from SECURITY.md §5) before any write/admin endpoint.
- [ ] Real DGCA reference series ingestion for backtest.

### Notes

- SQLite drops tzinfo on DateTime round-trip (`collected_at` returns naive ISO strings); PostgreSQL preserves it. Prototype-acceptable, fix if it matters to the dashboard.
- Weekly frequency buckets are means of available daily values (partial edge weeks included).

------------------------------------------------------------------------

# 2026-09-08 --- React Dashboard: Airspace Observatory Shell + 9 Screens

**Status:** DONE

### Objective

- Build the React dashboard consuming the FR-16 endpoints, per the Airspace Observatory spec (`UI_UX_DESIGN.md`) and TRD §2.4/§13 frozen stack.

### Work Completed

- [x] Vite + React 19 + TypeScript scaffold in `frontend/` (TRD §2.4 stack: Tailwind CSS v4, Apache ECharts 6, TanStack Query 5, React Router 7).
- [x] App shell: sticky header with Index Pulse (APIx + MoM + data-mode badge — REPLAY shown honestly, never as "live"), left rail nav, evidence/quality/methodology footer strip, skip-link, `/` command palette (navigate + search routes/airlines).
- [x] Typed API client mirroring all Pydantic schemas + react-query hooks (`frontend/src/api/`); consumed same-origin via Vite dev proxy → backend CORS allowlist stays empty (SECURITY.md §12).
- [x] 9 pages: Overview (hero + Index Pulse trend + Route Pressure movers + Data Confidence), Index (route/lead/frequency/from filters, dataZoom brush, base-100 markline), Route Observatory (SVG India map with route arcs colored by 7D change, airport heatmap matrix, all-routes table), evidence drawer (route index, per-lead-time median consumer-payable fares with quote/source counts, confidence bar, lead-time premium tile), Lead-Time curve (median fare vs days-to-departure + premium tiles), Fare Decomposition (stacked base/taxes/mandatory/convenience with ₹/% toggle, FR-09 note), Sources (cross-source consensus bars + median spread + registry + health), Quality cockpit (usable/sold-out/duplicate/rejection tiles, meters incl. imputation=0 policy note, source health, 7/30/90-day windows), Backtesting (metric tiles + honest non-equivalence disclaimer), Methodology (6-stage index recipe, expandable; versioned facts; basket table with placeholder-weight note).
- [x] Airspace Observatory tokens as Tailwind v4 theme (ink/paper/surface/muted/grid/signal/warning/critical/positive + radar dark-canvas for the map), tabular numerals class, visible focus rings, reduced-motion support.
- [x] Empty states ("no valid observations" with suggestions), error states (no stack traces), loading states on every query.

### Technical Changes

- Vite dev proxy `/api` and `/health` → 127.0.0.1:8000; no CORS config needed anywhere.
- Per-route 7D movers/series fetched client-side from `/index/history?route_id=…&frequency=DAILY` (10 small requests, cached by TanStack Query; `/route/{id}` exists but query-param form shares the cache key shape).
- Median computations client-side with a 5-line helper (mirrors engine policy: consumer-payable, AVAILABLE-only, sold-out ≠ zero).
- Route map is a schematic (airport lon/lat → linear projection onto SVG viewBox, quadratic-arc lift); deliberately not survey-grade per spec §9 "stylized".

### Files Changed

``` text
- frontend/ (new: package.json, vite.config.ts, tsconfig*, index.html)
- frontend/src/{main.tsx, App.tsx, AppRoutes.tsx, index.css}
- frontend/src/api/{types.ts, hooks.ts}
- frontend/src/components/{ui.tsx, Chart.tsx, CommandPalette.tsx}
- frontend/src/lib/{format.ts, airports.ts}
- frontend/src/pages/{Overview, IndexPage, RoutesPage, LeadTimePage, FareDecompositionPage, SourcesPage, QualityPage, BacktestingPage, MethodologyPage}.tsx
```

### Tests

``` text
Command: npx tsc -b && npm run build; uvicorn + vite dev + curl smoke
Result: typecheck clean; build ok (85.4 kB gzip js / 5.1 kB css); all 9 page modules + proxy endpoints 200; /api/v1 routes, history, quality, backtests verified through proxy; backend tests still 42 passed.
```

### Data/Statistical Changes

- None — read-only consumption of existing endpoints.

### Security Changes

- Same-origin via dev proxy; no new CORS entries. Public GET-only app; no secrets, no auth surface added.

### UI/UX Changes

- Airspace Observatory shell implemented as specced: rail+palette navigation, Index Pulse header, footer evidence strip, evidence drawer, lead-time curve, quality cockpit, methodology recipe, confidence bars ("Data Confidence Score", never "Confidence Interval"), non-color-only status (▲▼■ + labels), honest REPLAY mode badge and non-DGCA/non-CPI disclaimers.

### Decisions

- Tailwind v4 (current major; CSS-first `@theme` tokens instead of tailwind.config) — visual system unchanged from spec.
- Lazy-loaded routes (`React.lazy`) for the 9 pages; single-bundle build stays ~85 kB gzip.
- Map arc colors reuse positive/critical/signal hues; heatmap uses tinted cell backgrounds + signed glyphs.
- Overview "Route Pressure" computes 7D change client-side from route series (endpoint gives only latest value) — deterministic arithmetic, no new backend surface.

### Blockers

- None. (No headless browser on this machine — visual smoke was done via HTTP/proxy checks; playwright lands with the first real adapter task.)

### Next Steps

- [ ] First live source adapters + APScheduler behind FlightSource contract.
- [ ] Auth (JWT + RBAC) before any write/admin endpoint.
- [ ] Anomaly screen (price-shock detection, UI_UX_DESIGN.md §20) once an anomaly endpoint or client-side rule exists.
- [ ] Docker Compose + serving built frontend when daemon available.

### Notes

- Backend serves naive ISO timestamps from SQLite (known, log 2026-09-08) — UI uses toLocaleString which tolerates both.

------------------------------------------------------------------------

# 2026-09-08 --- One-Command Pipeline: make.sh (Linux) + make.bat (Windows)

**Status:** DONE

### Objective

- Automate the whole stack (env → replay data → seed → index → backtest → tests → API → dashboard) behind a single command on both Linux and Windows.

### Work Completed

- [x] `make.sh`: full pipeline with modes `--serve` (servers only), `--stop`, `--test`, `--fresh-data`, `--keep` (passed through to seed.py); creates venv + installs requirements if missing; npm install on first run; health-checks API (`/health`) and dashboard before declaring success; pidfiles in `/tmp/airstat/` + port-based kill for orphans.
- [x] `make.bat`: Windows equivalent (cmd, no PowerShell dependency), same modes; logs in `%TEMP%\airstat`.
- [x] README quick-start rewritten around the one-command entry; manual steps kept below it.

### Technical Changes

- Vite dev server binds IPv6 `[::1]` by default → dashboard health probe uses `localhost`, not `127.0.0.1`.

### Files Changed

``` text
- make.sh (new, chmod +x)
- make.bat (new)
- README.md (quick start + repo layout)
```

### Tests

``` text
Command: ./make.sh (full run), ./make.sh --serve, ./make.sh --stop, ./make.sh --test; bash -n make.sh
Result: full pipeline green — replay skipped (present), seed + 42 tests passed, API healthy, dashboard healthy, proxy endpoint verified (index/latest through :5173). --stop cleanly killed both pidfile pids. make.bat syntax-reviewed only (no Windows machine available here).
```

### Data/Statistical Changes

- None (pipeline re-run produced the same deterministic seed).

### Security Changes

- None — same read-only servers, same-origin proxy; no new exposed ports beyond 8000/5173 loopback.

### UI/UX Changes

- None.

### Decisions

- Plain bash + cmd (not Makefile/just/task) — zero extra tooling, works on both targets with identical interfaces.
- make.bat is untested on real Windows (no Windows machine in this session) — flagged as the known limitation; structure mirrors make.sh 1:1.
- make.sh takes a pid-based pipeline lock (`/tmp/airstat/pipeline.lock`) — two concurrent seeds corrupt the SQLite DB (verified the hard way: an overlapping verification run caused `database is locked` errors and a partial re-ingest with zero index values; clean re-run restored everything).

### Blockers

- None.

### Next Steps

- [ ] Teammate with a Windows box runs make.bat once and reports.

------------------------------------------------------------------------

# 2026-09-08 --- Git Configuration: Comprehensive .gitignore

**Status:** DONE

### Objective

- Update root `.gitignore` with comprehensive patterns covering Python, Node/Vite, secrets, SQLite databases, runtime logs, OS/IDE files, and agent caches.

### Work Completed

- [x] Expanded `.gitignore` from minimal 9-line stub to comprehensive 115-line standard covering all stack components.
- [x] Ensured secrets policy compliance (SECURITY.md: `.env*`, `*.pem`, `*.key`).
- [x] Added coverage for Python cache/builds/venvs, pytest, coverage, mypy, ruff.
- [x] Added coverage for frontend build artifacts (`dist-ssr`, `.vite`, `.oxlintcache`, logs).
- [x] Added database and sqlite artifacts (`*.db`, `*.sqlite*`, WAL/journal files).
- [x] Added agent cache exclusions (`graphify-out/`, `graph.json`, `.gemini/`).

### Files Changed

``` text
- .gitignore (updated)
- log.md (updated)
```

### Tests

``` text
Command: .venv/bin/python -m pytest backend/tests -q
Result: 42 passed
```

------------------------------------------------------------------------

# Development Entry Template

\## YYYY-MM-DD ---
```{=html}
<Title>
```
**Status:** TODO / IN PROGRESS / DONE / BLOCKED

### Objective

-   

### Work Completed

-   \[ \]

### Technical Changes

-   

### Files Changed

``` text
-
```

### Tests

``` text
Command:
Result:
```

### Data/Statistical Changes

-   

### Security Changes

-   

### UI/UX Changes

-   

### Decisions

-   

### Blockers

-   

### Next Steps

-   \[ \]

### Notes

-   

------------------------------------------------------------------------

# Release Checklist

## v0.1 --- Foundation

-   [ ] Repository
-   [ ] Docker
-   [ ] PostgreSQL
-   [ ] FastAPI
-   [ ] React
-   [ ] CI

## v0.2 --- Data

-   [ ] Schema
-   [ ] Migrations
-   [ ] Replay dataset
-   [ ] Validation
-   [ ] Normalization

## v0.3 --- Statistical Engine

-   [ ] Basket
-   [ ] Weights
-   [ ] Base period
-   [ ] APIx
-   [ ] Quality scoring
-   [ ] Backtest

## v0.4 --- Collectors

-   [ ] Adapter interface
-   [ ] Source 1
-   [ ] Source 2
-   [ ] Source 3
-   [ ] Source health
-   [ ] Ethical scraping controls

## v0.5 --- Dashboard

-   [ ] Overview
-   [ ] Route Observatory
-   [ ] Lead-time
-   [ ] Heatmap
-   [ ] Quality
-   [ ] Backtest
-   [ ] Methodology

## v1.0 --- SIH Demo

-   [ ] Security review
-   [ ] Automated tests
-   [ ] Demo mode
-   [ ] Replay mode
-   [ ] API documentation
-   [ ] Architecture documentation
-   [ ] SIH presentation
-   [ ] Final demo rehearsal
