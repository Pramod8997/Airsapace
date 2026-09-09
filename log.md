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

# 2026-09-08 --- "All pages empty": Root Cause Found + Fixed (AppRoutes never mounted)

**Status:** DONE

### Objective

- User reported every dashboard page rendering empty; suspected a color-schema issue.

### Root Cause

- `AppRoutes` (defines all 9 lazy routes/pages) was **never imported or mounted anywhere**. `App.tsx` rendered `<Outlet />`, but App is not a layout route with children, so Outlet returned `null` → `<main>` empty on every URL. Silent: no console error, no Suspense fallback (fallback only covers lazy-import suspense, not a missing router).
- Fingerprint that confirmed it: backend access log showed only app-shell queries (latest/quality/routes/airlines from header/footer/CommandPalette); zero page-level queries ever fired.

### Work Completed

- [x] Full audit: `tsc` clean, `vite build` clean, all dev modules HTTP 200, all API endpoints returning data — ruling out compile/CSS/API causes.
- [x] Reproduced in clean headless Chromium (playwright-core, no extensions/cache): `#main` had 0 children on every route, zero console errors.
- [x] Fix: `App.tsx` now imports and renders `<AppRoutes />` inside `<main>` (replaces the dangling `<Outlet />`); dropped unused `Outlet` import.
- [x] Verified in headless browser: `/`, `/index`, `/routes`, `/sources`, `/methodology` all render live content (APIx 99.49, route observatory, methodology recipe), zero console/page/request errors.
- [x] `tsc -b` + `vite build` pass after fix.

### Files Changed

``` text
- frontend/src/App.tsx (mount AppRoutes; remove dead Outlet)
- log.md (updated)
```

### Notes

- The uncommitted Overview hook-order fix (hooks before early return) is still in the working tree and still correct — keep it.
- User's screenshot showed a dark sidebar; this app is light-themed in a clean browser (navBg white) — likely a dark-mode browser extension on the user's side. Cosmetic only; unrelated to the empty pages.

### Next Steps

- [ ] Commit both frontend fixes (AppRoutes mount + Overview hook order).

------------------------------------------------------------------------

# 2026-09-08 --- Public GitHub README + Screenshot Assets

**Status:** DONE

### Objective

- Professional, attractive, emoji-free README for GitHub; keep the existing build-docs README separate and untracked.

### Work Completed

- [x] Captured six full-page dashboard screenshots via headless Chromium (Overview, Route Observatory, Index, Data Quality, Methodology, Backtest) into `docs/screenshots/` — chart canvases verified rendered.
- [x] Wrote new `README.md`: problem framing, pipeline stages, index methodology (formula, determinism, missing-data/outlier policies), architecture, verified tech stack, quick start, API table, dashboard screens, statistical-honesty section, repo layout, doc links. Shields badges (text only). Zero emoji (checked programmatically).
- [x] Moved old README to `README_internal.md` — already covered by the pre-existing uncommitted `.gitignore` entry; confirmed ignored via `git check-ignore`.
- [x] Re-ran backend tests after changes: 42 passed.

### Files Changed

``` text
- README.md (new public README; old content moved out)
- README_internal.md (local-only, gitignored)
- docs/screenshots/*.png (new, 6 files)
- log.md (updated)
```

### Notes

- README claims verified against the running system: 42 tests, 10 routes / 5 lead-time windows / ~14.6k replay observations, base period 2026-06-25 to 2026-07-24, methodology APIX-v1.0.

------------------------------------------------------------------------

# 2026-09-08 --- .gitignore Fix: `lib/` Pattern Was Ignoring Frontend Source

**Status:** DONE

### Root Cause

- The Python-packaging boilerplate pattern `lib/` (unanchored) also matched `frontend/src/lib/` — `airports.ts` and `format.ts` were ignored and **never committed**, so a fresh clone of the repo could not build the frontend (`App.tsx` and pages import from `./lib/format`).

### Work Completed

- [x] Anchored `lib/` and `lib64/` to the repository root (`/lib/`, `/lib64/`) with an explanatory comment.
- [x] Verified `frontend/src/lib/*.ts` now appear as untracked (ready to commit) and no other project source files are wrongly ignored (swept `git status --ignored` excluding venv/caches: only `README_internal.md` and `data/airstat.db` remain ignored, both intentional).

### Files Changed

``` text
- .gitignore (anchored lib/ lib64/)
- log.md (updated)
```

### Next Steps

- [ ] Commit `frontend/src/lib/airports.ts` and `frontend/src/lib/format.ts` together with the pending changes — the repo is broken on GitHub without them.

------------------------------------------------------------------------

# 2026-09-08 --- Compliance Audit vs PS-26056 + UI Polish (radar map fix)

**Status:** DONE

### Objective

-   Audit the build against the PRD (FR-01..FR-20, §15) and Problem Statement 26056; apply light UI polish that keeps the frozen Airspace Observatory identity; fix the invisible route-map labels.

### Work Completed

-   [x] Full read-only compliance audit (backend/pipeline/engine + frontend/dashboard). Result summary: statistical core, canonical model, deterministic Laspeyres index, lead-time indices, 10 API endpoints and 10 dashboard screens are DONE; primary gaps are real scraping engine (synthetic only), backtest reference (circular synthetic, not DGCA), auth/RBAC + admin writes (FR-20), runtime source resilience (FR-19), scheduler (FR-05), UI export (FR-17), and the Anomaly/Shock screen.
-   [x] **Fixed Route Observatory map bug:** airport nodes/labels were hardcoded near-white (`#f7f8fa`) over a *transparent* (white) card → invisible. Painted the intended dark radar canvas (`--color-radar #0a0f1a`) with a radial glow + refined navy graticule; labels now light-on-dark (`#e7ecf5`) with a `paint-order` halo for legibility over arcs. Verified by rasterizing the exact SVG.
-   [x] UI polish (identity unchanged): header Index-Pulse "radar ping" shown **only** when `data_mode === LIVE` (no ping for DEMO/REPLAY — statistical honesty); active nav-rail accent bar; subtle card/tile elevation (`--shadow-card`); thin instrument-style scrollbars; selection tint; new derived tokens `--color-surface-2`, `--color-signal-strong`.

### Technical Changes

-   `index.css`: added `surface-2`/`signal-strong` theme tokens, `--shadow-card`/`--shadow-pop`, `.obs-card`/`.obs-hover`, `.pulse-dot` + `@keyframes pulse-ring`, `::selection`, thin scrollbars. Reduced-motion block still disables the pulse.
-   `App.tsx`: LIVE-only pulse dot (inline `--dot` CSS var, `CSSProperties` cast); active-nav left accent bar; subtle sticky-header shadow.
-   `components/ui.tsx`: `Card` + `MetricTile` gain `.obs-card` elevation.
-   `pages/RoutesPage.tsx`: `RouteMap` rewritten to paint the dark canvas (defs radial gradient, dark rect, refined graticule, glowing nodes, halo labels, lighter title).

### Files Changed

``` text
- frontend/src/index.css
- frontend/src/App.tsx
- frontend/src/components/ui.tsx
- frontend/src/pages/RoutesPage.tsx
- log.md (this entry)
```

### Tests

``` text
Command: npx tsc -p tsconfig.app.json --noEmit   → exit 0 (clean typecheck)
Not run here: vite production build (Linux sandbox has only the win32 rolldown native binding — run on the Windows host); backend pytest (committed .venv is Windows/py3.14 + pip network-blocked). Engine math independently re-derived 12/12 in the audit.
```

### UI/UX Changes

-   Polish only; no change to the frozen Airspace Observatory palette/typography/layout. The route map now renders as the intended dark radar inset (previously blank-looking with invisible labels).

### Decisions

-   Map fix approach = paint the dark radar canvas (the `--color-radar*` tokens already existed and every map element was authored for a dark background) rather than recolour the map to light. No frozen decision changed.

### Blockers

-   None new.

### Next Steps (ranked, from audit)

-   [ ] Implement at least one real source adapter behind `FlightSource` (Playwright/Scrapy) — the PS-core "automated web scraping" gap.
-   [ ] Replace the circular synthetic backtest reference with a real DGCA monthly average-fare series; label "(not DGCA)" wherever metrics show until then.
-   [ ] FR-20: JWT auth + RBAC, write/admin endpoints, and actually write `AuditLog`.
-   [ ] FR-19 runtime resilience (rate-limit, backoff, CAPTCHA detect, pause, fallback); FR-05 APScheduler; FR-17 UI export (CSV/JSON/XLSX); Anomaly/Price-Shock screen.

### Notes

-   Audit was read-only; only the four frontend files above were modified. No backend or statistical code touched.

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

------------------------------------------------------------------------

# 2026-09-09 --- DGCA Route Weights (replaces placeholder)

**Status:** DONE

## What

Replaced the placeholder route-weight dict in `scripts/seed.py` with weights
derived from real DGCA city-pair passenger data, closing the "weights must be
sourced and versioned" open question for route weights.

-   Downloaded and parsed `data/fixtures/dgca_citypair_jul2026.xlsx` (DGCA
    "DOM CITYPAIR DATA, JULY 2026", public S3). Sheet layout: one row per
    unordered city pair, columns `PASSENGERS TO CITY 2` / `PASSENGERS FROM
    CITY 2` (directional). Mumbai appears as two airport rows (Mumbai +
    Navi Mumbai), both summed into the city pair.
-   New `scripts/load_dgca_weights.py`: parses the workbook, computes each
    basket route's share of total basket-route passengers (directional,
    normalized over the 10 basket routes, sums to 1.0), writes
    `data/fixtures/dgca_citypair_weights.json` (source, url, route_weights,
    route_pax). `--refetch` re-downloads from DGCA S3. openpyxl added to
    `requirements.txt` and installed into `.venv`.
-   `scripts/seed.py`: `seed_registries` now calls `load_route_weights()` —
    DGCA fixture when present (validated: all routes, sum ≈ 1.0), placeholder
    dict as fallback. `WEIGHT_VERSION="WB-2026.09-DGCA"`, `WEIGHT_SOURCE="DGCA
    DOM city-pair passenger data (July 2026)"`. Lead-time weights unchanged
    (still booking-distribution placeholder). No index-calculation changes.
-   New `backend/tests/test_dgca_weights.py` (6 tests).

## Computed weights (July 2026 pax)

| Route | Pax | Weight |
|---|---|---|
| DEL-BOM | 258,552 | 0.1655 |
| BOM-DEL | 245,999 | 0.157465 |
| DEL-BLR | 192,916 | 0.123486 |
| BLR-DEL | 189,511 | 0.121306 |
| BOM-BLR | 171,914 | 0.110043 |
| HYD-DEL | 120,755 | 0.077296 |
| CCU-DEL | 112,824 | 0.072219 |
| DEL-CCU | 108,324 | 0.069338 |
| BLR-HYD | 81,618 | 0.052244 |
| MAA-DEL | 79,837 | 0.051104 |
| Total | 1,562,250 | 1.000001 |

## Tests

`python -m pytest backend/tests/` — 54 passed (6 new).

## Notes

-   DGCA city-pair rows are direction-specific via the two passenger columns;
    each basket direction gets its own share (asymmetric: DEL-BOM ≠ BOM-DEL).
-   Weight semantics are versioned: `WB-2026.09-DGCA`; source URL baked into
    the fixture JSON.

------------------------------------------------------------------------

# 2026-09-09 --- MoSPI CPI Airfare reference loader (replaces synthetic backtest reference)

**Status:** DONE

## What

-   Deep research confirmed DGCA never published monthly average-fare data
    (memory.md §9 blocker). Official replacement reference: the MoSPI CPI
    "Airfare" sub-index (2024=100, All India, Combined, item code 294 /
    07.3.3.1.2.01), fetched from the eSankhyiki API
    `api.mospi.gov.in/api/cpi/getCpiData`.
-   New `collectors/sources/mospi_cpi.py` — reference-series loader (NOT a
    FlightSource): `fetch_cpi_airfare(years)` (ssl legacy-renegotiation
    workaround, 3 attempts with backoff), fixture save/load
    (`data/fixtures/cpi_airfare.json`), and `national_monthly_series()`
    (APIx daily national series -> monthly means so both sides of the backtest
    are monthly). Constant `CPI_REFERENCE_NAME`.
-   New `scripts/load_cpi_backtest.py` CLI (fixture by default, `--live` to
    refresh from the API then run).
-   `run_backtest()` in `backend/app/services/index_runner.py` gained an
    optional `actual_series` parameter (pre-resampled points; defaults to the
    daily national series — backwards compatible).
-   `scripts/seed.py` `make_reference_and_backtest`: CPI fixture first, live
    fetch second, clearly-labeled synthetic fallback only if both fail.
-   Live fixture saved from the API: 6 months (2025-10 → 2026-07; gaps where
    eSankhyiki has no 2024-base rows). Verified anchors: 2026-06 = 126.09,
    2026-05 = 127.62, 2026-07 = 125.46.

## Honesty note

CPI item is monthly All-India consumer index; APIx is a daily national index
over route × lead-time fares. `compute_metrics` correlation/trend-direction
report co-movement only — never methodological equivalence. Backtest metrics
on the current demo replay data (2 overlapping months, n=2): correlation
-1.0 — statistically meaningless at n=2 and not presented as a result.

## Tests

`python -m pytest backend/tests/test_mospi_cpi.py -q` — 4 passed, 1 skipped
(live fetch behind `CPI_LIVE=1`). Full suite: 58 passed, 1 skipped.

------------------------------------------------------------------------

# 2026-09-09 --- Real source adapters: Yatra OTA + Akasa Air tariff sheet

**Status:** DONE

## What

First two genuinely compliant REAL sources (from the completed compliance
research), built against the same `FlightSource` contract as the sim feed:

-   `collectors/sources/yatra.py` — Yatra OTA. robots.txt is
    `User-agent: * / Allow: /`, the `/cheap-flights/search/<city1>-to-<city2>-flights`
    pages are sitemap-published, ToS has no anti-bot clause. Collects the
    server-rendered 7-day cheapest-fare strip (one quote per day,
    airline="MULTI", no per-flight prices — they are JS-rendered and never
    fabricated). Fixture mode by default (`data/fixtures/yatra_*.txt`),
    live mode behind `YATRA_LIVE=1` (declared UA, 30s timeout, 10s politeness
    sleep between route fetches; plain httpx — TODO comment to route through
    EthicalHttpClient when scrape_engine v2 lands, since it was mid-rewrite by
    another agent and is not present yet).
    `POLICY_STATUS = "ROBOTS_ALLOWED_SEO"`.
-   `collectors/sources/akasa_tariff.py` — Akasa Air published fare-sheet PDF
    (robots.txt: zero Disallow lines; plain HTTP 200 storyblok URL). Parses
    `pdftotext -layout` output: Minimum row's `Fare_Level_1` = base_fare
    (the lowest filed tariff — levels 2..15 and Maximum rows are RBD
    buckets/ceilings, a different statistic, not collected), YQ fuel charge =
    taxes, advance_days=1 (tariff is advance-agnostic; documented
    convention), airline "QP", fare_class "FARE_LEVEL_1". "Updated on:" date
    (1-Sep-26) parsed and surfaced via `health_check`. `fetch_pdf()` live
    refetch behind `AKASA_LIVE=1`. `load_akasa_tariff(session, day)` ingest
    helper (JobSpec + ingest_quotes, same pattern as collect_demo.py).
    `POLICY_STATUS = "PUBLISHED_TARIFF_PDF"`.
-   Fare-component honesty: both sources publish single all-in figures with no
    base/tax split, but `quote_payable_fare` returns None unless base+taxes+
    mandatory_fees are all present — so the all-in figure is carried as
    `base_fare` with `taxes=0, mandatory_fees=0` (consumer_payable ==
    total_fare exactly; no component split is invented). Validity,
    consistency and timestamp quality components all score 1.0; parsed
    quotes score 0.86-0.91 under QS-v1 and ingest as AVAILABLE.

## PDF structure discovered (Akasa sheet)

48 directional markets (origins Agartala→Calicut only — no DEL/MAA-origin
rows), each with Minimum and Maximum rows × 15 fare levels, stops and fuel
charge (YQ, 0 everywhere in this issue). Effective date 1-Sep-26. Page 2 is a
per-airport fee table (not a tariff grid). Basket coverage: BLR-DEL (2393),
BLR-BOM (1168 via Mumbai + 1138 via Navi Mumbai — both mapped to BOM),
BLR-HYD (638). DEL-BOM/BOM-BLR/DEL-CCU/CCU-DEL are NOT covered (no
Delhi/Kolkata/Mumbai-origin markets).

## Intended seed/demo integration (NOT wired — other agents own seed.py)

In `scripts/seed.py` `seed_registries`, after the sim-source block:

```python
from collectors.sources.akasa_tariff import POLICY_STATUS as AKASA_POLICY
from collectors.sources.yatra import POLICY_STATUS as YATRA_POLICY
session.add(Source(id="akasa-tariff", name="Akasa Air fare sheet (published tariff PDF)",
    source_type="AIRLINE", adapter_name="akasa-tariff", adapter_version="1.0",
    policy_status=AKASA_POLICY, robots_status="ALLOWED_NO_DISALLOWS",
    rate_limit_per_hour=6, active=True, reliability=0.98))
session.add(Source(id="yatra-ota", name="Yatra (SEO route pages, robots allowed)",
    source_type="OTA", adapter_name="yatra", adapter_version="1.0",
    policy_status=YATRA_POLICY, robots_status="ALLOWED",
    rate_limit_per_hour=12, active=True, reliability=0.90))
```

then in the demo cycle: `load_akasa_tariff(session, day)` for Akasa, and for
Yatra per route × day-strip advance bucket:
`YatraSource().search(FlightSearchQuery(origin, dest, departure_date=day+lead, advance_days=lead))`
→ `ingest_quotes(...)` with `lead_time=lead` — noting the strip gives leads
6-13 (DEL-BOM) / 7+ (others), not the frozen 1/7/15/30/45 buckets, so the
seed integration phase must decide whether to snap to nearest basket lead or
extend the lead registry.

## Tests

New `backend/tests/test_yatra.py` (10 tests) and
`backend/tests/test_akasa_tariff.py` (8 tests): day-count 7, expected fares
(6529/7376/5050 families), Sept-2026 dates, schema validity, advance_days
consistency, fare arithmetic (total=base+taxes), payable flows through,
effective date parsed, day-strip regex immune to flight-block date formats.
Full suite: 80 passed, 1 skipped.

------------------------------------------------------------------------

# 2026-09-09 --- Lead-time elasticity visual + real-sources compliance doc

**Status:** DONE

## What

-   `frontend/src/pages/LeadTimePage.tsx`: added the PRD §"lead-time
    elasticity curves" deliverable below the existing fare-vs-lead chart.
    Deterministic client-side arithmetic (no backend change): per route,
    `premium_pct(lead) = (median(lead)/median(T+1) - 1) * 100` over the same
    AVAILABLE-quotes snapshot. New "Lead-Time Elasticity" section: premium
    curve chart (x: T+1..T+45, y: premium %, one series per route, route
    selector matching the page's existing pattern, dashed zero reference
    markLine, top-5-routes default), 3 summary tiles (max premium route,
    avg deep-lead discount, routes with curve), empty/loading/error states
    per house pattern, and an explicit footer note that this is descriptive
    analytics and NOT part of the index calculation.
-   `frontend/src/pages/SourcesPage.tsx`: source registry now renders
    policy_status as styled badges (positive token for PUBLISHED_TARIFF_PDF
    and ROBOTS_ALLOWED_SEO; neutral for DEMO_SCRAPING_COMPLIANT / SIMULATED
    / SYNTHETIC_DATA), plus an honest legend line per status (e.g.
    "PUBLISHED_TARIFF_PDF — airline-published filed fares, not transaction
    prices") and a "Compliance research" link to the new doc. `policy_status`
    already flowed through the API (`SourceOut`, schemas.py:96) — backend
    untouched.
-   `docs/research_sources.md` (NEW): the source-compliance decision matrix
    from the deep research — 16-source table (IndiGo, Air India, Air India
    Express, Akasa, SpiceJet, Alliance Air, MMT, Goibibo, Yatra, EaseMyTrip,
    Cleartrip, Ixigo, Amadeus, Travelpayouts, MoSPI CPI, DGCA) with
    robots.txt verdict (rules quoted where we have them: Yatra `Allow: /`,
    Akasa zero disallows, MMT `Disallow: /flight/search*`), ToS verdict,
    anti-bot stack, decision (BUILT / COMPLIANT-AVAILABLE /
    RESTRICTED-DOCUMENTED / REJECTED), and usage; the DGCA fare-data finding
    (route-wise monthly average fares never published — CPI Airfare sub-index
    is the official anchor, DGCA city-pair data provides weights); and the
    compliance policy statement (robots+ToS first, detection-never-bypass, no
    IP rotation, CAPTCHA pause, honest policy_status labeling).

## Files Changed

``` text
- frontend/src/pages/LeadTimePage.tsx (elasticity section + tiles + note)
- frontend/src/pages/SourcesPage.tsx (policy badges + legend + doc link)
- docs/research_sources.md (new)
- log.md (this entry)
```

## Tests

``` text
Command: cd frontend && npx tsc -b && npm run build
Result: both clean (tsc silent; build ✓ built in 943ms). Backend untouched —
no backend tests run (policy_status was already exposed).
```

## Data/Statistical Changes

-   None to the index. Elasticity is descriptive client-side analytics over
    the fare snapshot; explicitly disclaimed on-page as not part of index
    calculation.

## Security Changes

-   None (read-only UI; backend not touched).

## Next Steps

-   [ ] Consider deeper route-lead coverage once more real sources land.


# 2026-09-09 --- Anomaly detection module (engine + API + Anomalies screen)

**Status:** DONE

## Completed

-   [x] `statistical_engine/anomaly.py` — rule-based, deterministic candidate
    price-shock detection (ANOMALY-v1). Per (route, lead time): trailing
    window median vs latest-day median of AVAILABLE non-outlier quotes;
    flags when |change| >= threshold AND source consensus (>=3 sources or
    >=60% same-direction, with >=2 sources so 1/1 is never "consensus").
    Severity SHOCK (>=2x threshold) / ELEVATED / DIP; sold-out share and a
    §20 evidence dict per record. Docstring states candidate-not-causation
    honesty and that it is never part of the index calculation.
-   [x] `GET /api/v1/anomalies` (window_days 7..365, threshold_pct 5..100,
    optional route_id) returning AnomalyReportOut with model_version, as_of,
    disclaimer. Read-only Python-side grouping over AVAILABLE/SOLD_OUT
    non-outlier quotes.
-   [x] `AnomalyPage.tsx` at `/anomalies` (nav entry, lazy route): §20 card
    signature (route arrow, ₹ current median, "+X% vs 30-day route median"),
    severity token styling (critical/warning/signal), expandable WHY?
    evidence, empty/loading/error states, disclaimer footer.
-   [x] `useAnomalies` hook + TS types mirroring the API contract.

## Files Changed

``` text
- statistical_engine/anomaly.py (new)
- backend/app/schemas.py (AnomalyOut, AnomalyReportOut)
- backend/app/api.py (GET /api/v1/anomalies)
- backend/tests/test_anomaly.py (new, 12 tests)
- frontend/src/api/types.ts, frontend/src/api/hooks.ts (Anomaly types, useAnomalies)
- frontend/src/pages/AnomalyPage.tsx (new)
- frontend/src/AppRoutes.tsx, frontend/src/App.tsx (route + nav)
- log.md (this entry)
```

## Tests

``` text
Command: .venv/bin/python -m pytest backend/tests -q
Result: 113 passed, 1 skipped (was 101 passed, 1 skipped).
Command: cd frontend && npx tsc -b && npm run build
Result: both clean.
```

## Data/Statistical Changes

-   None to the index. Anomaly detection is ML-adjacent read-only analysis;
    CLAUDE.md invariant honored (deterministic index engine untouched).

## Security Changes

-   Read-only GET with same validation patterns as existing endpoints.

## Next Steps

-   [ ] Surface anomalies on the Overview page once real multi-source data lands.

# 2026-09-09 --- Forecasting Layer: Holt Linear Exponential Smoothing + API + Overview Overlay

## Status

-   [x] Complete

## What Was Done

Auxiliary forecast layer for the national APIx series. Read-only: forecasting
never participates in the index calculation (CLAUDE.md invariant); every
surface carries the "Forecast — model extrapolation, not an observed price"
disclaimer.

- `statistical_engine/forecast.py` (new): `FORECAST-v1` — Holt's linear
  exponential smoothing (level + trend), deterministic grid search over
  alpha, beta in {0.1..0.9 step 0.1} minimizing one-step in-sample MSE;
  14-point holdout RMSE reported alongside in-sample RMSE; refuses < 20
  points; pure stdlib, no new dependencies.
- `backend/app/schemas.py`: `ForecastPointOut`, `ForecastOut`.
- `backend/app/api.py`: `GET /api/v1/forecast?horizon_days=1..30` (validated,
  404 with a clear message when history is insufficient; series from
  `national_series`, methodology defaults to latest published).
- `frontend/src/api/types.ts` / `hooks.ts`: `Forecast` types + `useForecast`.
- `frontend/src/pages/Overview.tsx`: Index Pulse chart gains a dashed forecast
  series (continues after the last observed point via a one-point bridge) plus
  a "7-day forecast" toggle chip (default on) and "Forecast (not observed)"
  legend/tooltip label.
- `backend/tests/conftest.py`: test dataset series extended 7 -> 30 index
  days so the forecast endpoint has >= 20 points (forecast invariant).
- `backend/tests/test_mospi_cpi.py`: removed a dead `TEST_START, BASE_DAYS,
  SERIES_DAYS` import that the conftest change would otherwise have broken.

## Tests

``` text
Command: .venv/bin/python -m pytest backend/tests/test_forecast.py -q
Result: 6 passed.
Command: .venv/bin/python -m pytest backend/tests -q
Result: 119 passed, 1 skipped (was 101/1 at branch point; includes the anomaly
        suite landed concurrently).
Command: cd frontend && npx tsc -b
Result: clean.
```

## Data/Statistical Changes

-   None to the index. FORECAST-v1 is an auxiliary read-only model; the
    deterministic index engine is untouched.

## Security Changes

-   Read-only GET; query params validated (horizon 1..30, methodology
    max_length); 404 paths don't leak internals beyond counts.

## Next Steps

-   [ ] Add prediction-interval band (e.g. ±1.96 x holdout RMSE) if the demo
        warrants showing uncertainty visually.

------------------------------------------------------------------------

# 2026-09-09 --- Phase 3 Integration: Full Real-Data + ML-Layer E2E

**Status:** DONE

## Objective

- Wire all new real sources (Yatra, Akasa, Alliance) + CPI backtest + DGCA
  weights + ML auxiliary layer into one coherent, verified pipeline and demo.

## Completed

- [x] `scripts/collect_demo.py`: demo cycle now runs the full rotation —
  5 sim sources × basket + Yatra SEO strips (fixture-backed; YATRA_LIVE=1
  for live) + scrape-portal (robots-gated, participates when the portal is
  up, policy pauses recorded not bypassed) + Alliance/Akasa tariff PDF
  ingests per cycle (job-key idempotent).
- [x] Yatra lead-bucket convention documented: strip quotes carry their true
  advance_days (6-13); the JobSpec slot is lead_time=7 (nearest basket
  bucket). FareQuote.advance_days stays honest; outlier grouping unaffected.
- [x] `load_alliance_tariff` now filters to registry routes (14 non-basket
  sectors reported as skipped instead of crashing the seed).
- [x] Fresh seed E2E: 14,250 replay jobs + alliance tariff (9 stored,
  14 skipped) + DGCA weights (WB-2026.09-DGCA) + CPI backtest (official
  MoSPI series, n=2 overlap — demo-data limitation, labeled).
- [x] API E2E: 14 sources with honest policy_status labels;
  /anomalies (ANOMALY-v1, 0 anomalies on gentle seed data — correct);
  /forecast (FORECAST-v1, 7 points, alpha 0.9 beta 0.1); /backtests shows
  the MoSPI CPI reference.
- [x] Demo-cycle E2E: index moves (99.92 → 95.53 → 97.74); 721-739 quotes
  per cycle incl. Yatra + tariffs; with sim portal up the scraper path
  participates (robots allow, CAPTCHA 403s caught as SourcePolicyError).
- [x] Full verification: 119 passed / 1 skipped; tsc clean; vite build clean.

## Technical Changes

- Bytecode recovery: lost modules were decompiled from `__pycache__` .pyc
  (pycdc built from source — uncompyle6/decompyle3 don't support 3.10);
  serve_sim_portal recovered ~90%, scrape_engine rebuilt on the decompiled
  skeleton (ethical-v2 adds cf-mitigated/Akamai _abck/Reference# detection),
  alliance_tariff rebuilt from recovered docstring + fresh PDF (Wayback).
- httpx.ConnectError is not an OSError — demo loop catches
  (RuntimeError, OSError, httpx.HTTPError) for the down-portal case.

## Files Changed

```text
- scripts/collect_demo.py (full source rotation + tariff loaders)
- scripts/seed.py (CPI import fix, ALLIANCE_COLLECTION_DAY, 14-source registry)
- collectors/sources/alliance_tariff.py (registry-route filter, select import)
- backend/tests/test_api.py (source count 10 -> 14)
- data/fixtures/ (akasa_faresheet.pdf, dgca_citypair_jul2026.xlsx + weights
  json, cpi_airfare.json, yatra_*.txt x3, robots/ evidence x17,
  alliance_air_tariff_15MAR23.pdf recovered)
```

## Tests

```text
Command: .venv/bin/python -m pytest backend/tests -q; npx tsc -b; npm run build;
         fresh seed; API curl sweep; collect_demo with and without portal
Result: 119 passed / 1 skipped; tsc + build clean; all endpoints 200;
        demo cycle stores 721-739 quotes; index visibly moves.
```

## Security Changes

- None new — read-only surfaces; Yatra live mode still env-gated; portal
  catch is scoped to the demo loop only.

## Decisions

- Yatra strip advance_days kept honest (6-13) with lead_time=7 job slot —
  documented convention, honesty over bucket purity.
- Alliance non-basket sectors skipped-and-counted, not force-ingested.

## Blockers

- None. (CPI backtest overlap is n=2 on demo data — labeled, not blocking;
  a longer collection history grows the overlap naturally.)

## Next Steps

- [ ] Commit the whole session (large diff: rebuild + real sources + ML layer).
- [ ] Optionally: prediction-interval band on the forecast chart.
- [ ] Optionally: Amadeus adapter (free key) as the API-type real source.

------------------------------------------------------------------------

# 2026-09-09 --- `make.sh --demo`: One-Command Full Experience + DB Retention

**Status:** DONE

## Objective

- Fold portal + collector into the one-command pipeline with 1s cycles and
  bounded DB growth.

## Completed

- [x] `./make.sh --demo` (Linux) / `make.bat --demo` (Windows): full pipeline
  (seed → tests → API → dashboard) + sim portal (:8811) + collector loop at
  1s intervals. YATRA_LIVE=1 enables live Yatra fetching on top.
- [x] DB retention in `collect_demo.prune_demo_data`: every cycle drops
  observation tables older than 90 virtual days (window slides with the
  virtual clock; IndexValues + newest CalculationRuns never touched —
  immutable published results). Verified equilibrium: rows held ~54-55k
  while the window advanced; the June replay rows aged out automatically.
- [x] `--stop` kills all four processes (pidfiles + port sweep); make.bat
  uses wmic command-line match for portal/collector.
- [x] Fixed a real bug found in testing: a matched non-fall-through `case`
  branch made `--demo` exit silently with no output (bash case does NOT
  fall through to `*`); restructured with ARG normalization into the
  default branch.
- [x] E2E verified: index advancing (2026-09-25 → 2026-10-22 in ~3 min),
  ~1.4s per cycle (1s sleep + ~0.4s cycle), dashboard 200, forecast +
  anomalies endpoints live, 119 tests green.

## Files Changed

```text
- make.sh (--demo mode, portal/collector start/stop, PID tracking)
- make.bat (--demo mode, wmic-based stop)
- scripts/collect_demo.py (prune_demo_data + per-cycle retention)
```

## Tests

```text
Command: ./make.sh --demo (full E2E); .venv/bin/python -m pytest backend/tests -q
Result: pipeline green, 4 processes up, 1s cycling, DB bounded at ~90 virtual
        days of observations; 119 passed / 1 skipped.
```

## Decisions

- Demo retention = 90 virtual days hardcoded (production retention is a
  policy decision — documented in the function).
- Prune deletes observations but never IndexValues/CalculationRuns —
  published results are immutable even in demo mode.

## Next Steps

- [ ] Commit the session.
- [ ] Teammate runs make.bat --demo on Windows once.

------------------------------------------------------------------------

# 2026-09-09 --- Test-env hardening: YATRA_LIVE cannot flip tests to live mode

**Status:** DONE

## Objective

- Root-cause and fix a flaky-looking failure:
  test_search_uses_fixture_mode_by_default failed with 0 quotes + a live
  HTTP GET to yatra.com in the test log.

## Root Cause

- `YATRA_LIVE=1` leaked into the test process from the user's shell (set
  while trying live demo mode). The Yatra adapter then fetched the live
  page, whose raw HTML lacks the reader-proxy-rendered fare-strip format
  the parser targets → 0 quotes (honest empty, no fabrication) → assert
  failure. Nothing was wrong with fixture mode itself (verified by direct
  call and isolated test run).

## Work Completed

- [x] `backend/tests/conftest.py`: `os.environ.pop("YATRA_LIVE", None)` —
  tests now always run in fixture mode regardless of ambient shell env.
- [x] Verified both ways: normal run 119 passed / 1 skipped; with
  `YATRA_LIVE=1` force-exported, all tests still green, zero network calls.

## Files Changed

```text
- backend/tests/conftest.py (one line + comment)
```

## Tests

```text
Command: .venv/bin/python -m pytest backend/tests -q; YATRA_LIVE=1 .venv/bin/python -m pytest backend/tests/test_yatra.py -q
Result: 119 passed, 1 skipped; 14 passed (with the var exported)
```

------------------------------------------------------------------------

# 2026-09-10 --- PS-Alignment Pass: Backtest Depth, Engine Unification, Source Probe, Playwright JS Path, Scheduler

**Status:** DONE

## What

A clause-by-clause audit of PS 26056 against the actual code found five real
gaps; this pass closes all five. Parallel subagents were unavailable (API
quota/auth), so the work was done directly, phase by phase.

### 1. Backtest depth (was the weakest judge-visible point)

The CPI Airfare comparison aligned on only ~2 monthly points. Extended the
deterministic replay dataset from 75 days to 379 days
(`2025-08-25 → 2026-09-07`; `scripts/generate_replay_data.py` START/DAYS), moving
the base period to `2025-08-25 → 2025-09-23` (`scripts/seed.py`) so it precedes
the CPI window. Reseed: 72,010 jobs / 185,368 quotes. Backtest now aligns on
**all 6 published CPI months** (live-verified: the MoSPI API returns exactly
Oct-Dec 2025 + May-Jul 2026; 2024 is empty — 6 is the official ceiling):
`n_points=6, correlation=0.68, MAPE=6.3%`. Added regression test
`test_every_cpi_month_lies_inside_the_replay_window` so the window can never
silently shrink.

-   `replay_quotes.jsonl` untracked from git (96MB — at GitHub's 100MB file
    limit; deterministically regenerable; make.sh already regenerates).

### 2. Engine unification + collection resilience (TRD §12)

-   `ScrapeEngine.fetch_page`: bounded retry — up to 2 retries with
    exponential backoff on transient failures (network errors, 5xx); a
    429/503 `Retry-After` is honored once, capped at 60s. Policy stops
    (robots, 401/403, 429 without Retry-After, CAPTCHA) raise immediately
    and are never retried. New `fetch_bytes` (binary variant, PDF tariffs).
-   Yatra live path routed through the engine (closes the in-code TODO);
    Akasa `fetch_pdf` via `fetch_bytes` and made async (collect_demo awaits).
-   Akasa loader now iterates the Route registry (alliance pattern) instead
    of the single hardcoded BLR-DEL route.

### 3. Source probe — honest registry for every PS-named portal

New `scripts/probe_sources.py` (offline, table-driven from frozen research
`docs/research_sources.md` + `data/fixtures/robots/`): registers IndiGo, Air
India, Air India Express, SpiceJet, MakeMyTrip, Goibibo, EaseMyTrip,
Cleartrip, Ixigo as `active=False` with `RESTRICTED_DOCUMENTED` /
`REJECTED_ROBOTS_OR_TOS` + verbatim robots.txt evidence. Fixture
`data/fixtures/source_probe.json` committed; `--live` refreshes robots
evidence only (verdicts change only via the research doc). seed.py calls
`register_probed_sources`; SourcesPage gained the two badge styles.

### 4. Playwright JS-rendering path (PS names the toolchain)

New `collectors/sources/js_engine.py`: `JSScrapeEngine` renders with headless
Chromium **behind the identical compliance gate** (robots → rate limit →
declared UA render → CAPTCHA/anti-bot detect → SourcePolicyError pause).
Session = browser context. No stealth/evasion, ever. Import-guarded — nothing
depends on playwright being installed. Sim portal gained
`/flights/search-data` (JSON) + `/flights/search-js` (shell whose inline
script injects fares client-side — static httpx sees nothing, Playwright sees
the fares). `LiveSimPortalJS` source registered + in the collect rotation.
Real-browser end-to-end test passes (3 quotes rendered).

### 5. Scheduled daily extraction (TRD §11)

New `scripts/schedule_collect.py` (APScheduler, cron 08:00 IST, `--at`,
`--once`; coalesce + misfire grace; idempotent job keys). `collect_demo.py`
gained `--real-clock` (collect for TODAY instead of the virtual demo clock).

### Bug found and fixed during verification

The demo retention prune (`prune_demo_data`) deleted the methodology base
period once the replay window exceeded 90 days — "no observations in base
period" on the first post-change collect cycle. Root-cause fix: the prune
floor is now `base_period_end + 1`; the base period is never prunable.
Also: unregistered optional sources no longer kill a collect cycle
(ValueError caught with a re-seed hint).

## Files changed

-   `scripts/generate_replay_data.py`, `scripts/seed.py` — window + base period
-   `collectors/sources/scrape_engine.py` — retry, fetch_bytes, parse_fare_rows
-   `collectors/sources/yatra.py`, `collectors/sources/akasa_tariff.py` — engine routing, async PDF fetch, registry iteration
-   `scripts/probe_sources.py` (new), `data/fixtures/source_probe.json` (new)
-   `collectors/sources/js_engine.py` (new), `scripts/serve_sim_portal.py` — JS endpoints
-   `scripts/schedule_collect.py` (new), `scripts/collect_demo.py` — real-clock + prune fix + JS rotation
-   `backend/tests/` — test_scrape_engine (retry), test_yatra (engine wiring), test_mospi_cpi (window), test_probe_sources (new), test_js_engine (new), test_scheduler (new), test_api (counts 24)
-   `frontend/src/pages/SourcesPage.tsx` — RESTRICTED/REJECTED badges
-   `requirements.txt` — apscheduler, playwright (optional)
-   `make.sh` — `--schedule` mode (servers + daily 08:00 IST scheduler, one cycle now); scheduler pidfile in `--stop`; dependency re-check for venvs predating apscheduler; prune wording fix
-   `README.md`, `memory.md` — numbers, new sections, decisions
-   `.gitignore` — replay fixture untracked

## Verification

```text
Command: .venv/bin/python -m pytest backend/tests -q
Result: 152 passed, 1 skipped (CPI live opt-in)   [was 119 passed]

Command: .venv/bin/python scripts/seed.py (backtest line)
Result: n_points=6, mae=7.73, rmse=9.43, mape=6.31, correlation=0.68

Command: portal up + .venv/bin/python -m pytest backend/tests/test_js_engine.py -q
Result: 7 passed (incl. real-browser end-to-end render)

Command: timeout 30 .venv/bin/python scripts/schedule_collect.py --once
Result: scheduler starts, one real-clock cycle runs, next fire time printed

Frontend: npx tsc -b && npm run build → clean
```

## Known limitations

-   The backtest's APIx side is synthetic replay data (labeled as such); the
    comparison demonstrates the framework against the official series —
    co-movement framing only, never equivalence.
-   Mixing replay history with fresh sim collection shows a level shift at
    the data-mode boundary (replay carries a year of drift; sim anchors
    fresh) — visible on the Overview trend, honest, documented here.
-   Playwright browsers (~300MB) are optional; without them the JS portal
    source skips cleanly and everything else is unaffected.
