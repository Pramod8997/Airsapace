# AirStat India — Project Memory

**Purpose:** Persistent *current-state* record for the team and AI coding assistants. This file tracks what's true *right now* — frozen decisions, sprint, blockers, open questions. Reference material (stack, architecture, schema, formula) lives in `TRD.md`/`PRD.md`; this file points to it rather than copying it, so the two can't drift out of sync.

> Update after every meaningful development session. See `log.md` for the entry template — don't duplicate one here.

---

## 1. Project Identity

```text
Project: AirStat India | SIH 2026 | Problem Statement 26056 | Org: MoSPI | Theme: Smart Automation | Category: Software
```

Pipeline: `Observe → Validate → Normalize → Quality-score → Aggregate → Explain → Backtest → Publish`

---

## 2. Current Product Status

```text
Overall: Backend core + dashboard working end-to-end (replay → clean → index → backtest → API → UI)
Backend: WORKING — FastAPI, all FR-16 endpoints, 42 tests green (auth/RBAC deferred; no write endpoints yet)
Frontend: WORKING — React 19 + TS + Vite + Tailwind v4 + ECharts + TanStack Query; 9 Airspace Observatory screens; dev-proxy same-origin
Database: WORKING — SQLite dev default at data/airstat.db; PostgreSQL-ready via DATABASE_URL (TRD target unchanged)
Collectors: WORKING (real + demo mix) — FlightSource contract; 5 sim-live; ethical scraping engine v2 (robots gate RFC 9309-aware, rate limit, CAPTCHA/Akamai/Cloudflare detection, bounded retry with Retry-After honoring — never bypass, never retry policy stops); local demo portal (static + JS-rendered endpoints); REAL sources: Alliance Air tariff PDF, Akasa Air fare-sheet PDF (both PUBLISHED_TARIFF_PDF, fetched through the engine), Yatra SEO route fares (ROBOTS_ALLOWED_SEO, fixture-backed, YATRA_LIVE=1 for live, live path routed through the engine); OPTIONAL Playwright JS-rendering path (js_engine.py, same compliance gate, demonstrated on the sim portal's /flights/search-js); 9 PS-named portals registered active=False with frozen research verdicts (scripts/probe_sources.py). 24 sources, honest policy_status labels.
Statistical Engine: WORKING — APIX-v1.0 deterministic Laspeyres, MAD outliers, QS-v1 quality, versioned + input-hash fingerprinted; aux read-only layers: FORECAST-v1 (Holt linear, never touches index) + anomaly detection
Backtesting: WORKING — vs MoSPI CPI Airfare sub-index (2024=100, All India Combined; live eSankhyiki series, fixture committed); replay window 2025-08-25→2026-09-07 (379 days, 185k+ observations) covers all 6 published CPI months → n_points=6 (corr 0.68, MAPE 6.3%); verified live 2026-09-10 that the API returns exactly those 6 months (2024 empty) — 6 is the official ceiling; synthetic fallback only if fixture + live fetch both fail
Scheduling: WORKING — scripts/schedule_collect.py (APScheduler cron 08:00 IST, --at/--once); collect_demo.py gained real_clock mode; jobs idempotent on the TRD §11 key
Security: PARTIAL — headers, rate limit, validation, CORS allowlist; auth/RBAC/audit-write deferred
Testing: PASSING — .venv/bin/python -m pytest backend/tests -q → 152 passed, 1 skipped (CPI live opt-in); frontend: npx tsc -b && npm run build → clean
Deployment: NOT STARTED (Docker Compose when daemon available); one-command pipeline: ./make.sh (Linux) / make.bat (Windows) — venv→data→seed→tests→API→UI
```

---

## 3. Reference material (canonical location — don't copy here)

| Topic | Canonical source |
|---|---|
| Tech stack | `TRD.md` §2 |
| Architecture / data-flow diagram | `TRD.md` §3 |
| Repo layout | `TRD.md` §4 |
| Database entities/schema | `PRD.md` §10, `TRD.md` §7 |
| Canonical fare fields | `TRD.md` §6 |
| Index formula & versioning rules | `TRD.md` §9 |

Quick-reference only (kept here because it's one line and load-bearing): `I_t = [ Σ(w_i × P_i,t / P_i,0) / Σw_i ] × 100`, base index = 100.

---

## 4. Frozen Decisions

**Architecture**
- Modular source-adapter pattern; statistical engine independent of scraping.
- Raw observations preserved; index calculations versioned.
- Dashboard must not depend on live scraping for demo availability.

**Product**
- Route basket: 10 representative routes (list in `PRD.md` §14).
- Lead times: T+1, T+7, T+15, T+30, T+45.
- Prototype index: Laspeyres-style, base = 100.
- Sold-out ≠ zero. Missing ≠ zero.

**Ethical Collection**
- Respect robots.txt/ToS, rate-limit, detect CAPTCHA, stop when access is restricted, never bypass access controls.

**Engineering (2026-09-08)**
- Dev DB = SQLite via `DATABASE_URL` default (local Docker daemon off); PostgreSQL stays the production target — no PG-specific SQL in the codebase.
- Python 3.10 venv on this machine (no 3.12, 3.11 lacks ensurepip); code kept 3.10+ compatible.
- Prototype uses `create_all`; Alembic deferred until the schema stabilises.
- Backtest reference is the MoSPI CPI "Airfare" sub-index (exact CPI component APIx augments — strong framing for MoSPI judges). Never claim methodological equivalence: co-movement (correlation/trend-direction) framing only, and APIx is daily while the CPI item is monthly (APIx resampled to monthly means before comparing). Never present it as DGCA data — DGCA monthly average fares were proven unpublished.

**Agent Tooling** (2026-09-08)
- Claude Code plugins installed (user scope, this machine only — teammates install separately, commands in `prompt.md`): `ponytail` v4.9.0 (anti-overengineering discipline; active by default, mode `full`), `ui-ux-pro-max` v2.13.0.
- `graphify` (CLI 0.8.35 + skill) was already installed — nothing to install. Knowledge graph **not yet built**; run `/graphify .` when first needed. Its outputs (`graphify-out/`, `graph.json`) are kept out of agent context via `.claudeignore`.
- ui-ux-pro-max may generate design **only** when fed the Airspace Observatory direction (`UI_UX_DESIGN.md`) as the brief — never a generic "airfare dashboard" prompt. Its stack-agnostic accessibility/UX checks (resilient text, focus states, reduced-motion) are unrestricted.

---

## 5. Current Sprint

```text
Sprint: Real data layer + ML auxiliary layer (post core+dashboard)
Start: 2026-09-09
End: (open)

Primary objective: smallest correct system per CLAUDE.md §6, then make it impressive.

Tasks:
- [x] Canonical data model + cleaning + deterministic index + replay + backtest + API (2026-09-08, see log.md)
- [x] React dashboard consuming the API (Airspace Observatory, 9→11 screens) (2026-09-08/09, see log.md)
- [x] DGCA-derived route weights (WB-2026.09-DGCA, city-pair July 2026) (2026-09-09, see log.md)
- [x] CPI Airfare backtest reference replacing synthetic (2026-09-09, see log.md)
- [x] Real sources: Yatra (ROBOTS_ALLOWED_SEO), Akasa + Alliance tariff PDFs (2026-09-09, see log.md)
- [x] Ethical scraping engine rebuild incl. anti-bot detection; sim portal; full demo rotation (2026-09-09, see log.md)
- [x] ML auxiliary layer: ANOMALY-v1 (+ /anomalies + screen) + FORECAST-v1 (+ /forecast + Overview overlay) + lead-time elasticity (2026-09-09, see log.md)
- [x] Commit the session (large diff: rebuild + real sources + ML layer) (2026-09-09, commit 9f23ec7)
- [x] PS-alignment pass (2026-09-10, see log.md): 12-month replay window → backtest 6/6 official points; engine unification + bounded retry; source probe registry (9 PS-named portals, honest statuses); Playwright JS-rendering path; APScheduler daily collection
- [ ] Auth (JWT + RBAC) before any write/admin endpoint
- [ ] Commit the PS-alignment session (user decision on granularity)
```

## 6. Current Blockers

```text
- None / UPDATE
```

---

## 7. Important Assumptions

1. Source access can change over time.
2. Some sources may not permit automated collection.
3. Historical data may need a controlled replay dataset.
4. Public DGCA reference data may differ conceptually from APIx.
5. Route weights must be sourced and versioned.
6. The SIH prototype is an analytical augmentation, not a replacement for official CPI.

---

## 8. Decisions Log

| Date | Decision | Reason | Owner |
|---|---|---|---|
| 2026-09-07 | Use modular source adapters | Source websites change independently | Team |
| 2026-09-07 | Separate scraper from index engine | Statistical reproducibility | Team |
| 2026-09-07 | Build demo/replay mode | Protect SIH demo from live source failures | Team |
| 2026-09-07 | Use Airspace Observatory UI | Distinct analytical identity | Team |
| 2026-09-08 | Install agent plugins ponytail + ui-ux-pro-max (graphify already present) | Agent discipline + design intelligence per `prompt.md` | Team |
| 2026-09-08 | ui-ux-pro-max design generation only from the Airspace Observatory brief | Generic generator output conflicts with the frozen UI direction | Team |
| 2026-09-08 | Build backend core on SQLite dev default; PostgreSQL target unchanged | Local Docker daemon off; keep codebase portable | Team |
| 2026-09-08 | Duplicate = natural key (source+flight+cabin+class+instant); raw kept, processed skipped | Auditability without double-counting observations | Team |
| 2026-09-08 | Synthetic backtest reference series, explicitly labeled non-DGCA | Demo the backtest workflow before real DGCA data arrives | Team |
| 2026-09-08 | Frontend consumes API same-origin via Vite dev proxy; CORS allowlist stays empty | No dev-time CORS loosening; production serves frontend behind same origin | Team |
| 2026-09-08 | Tailwind v4 CSS-first tokens (not v3 config) — palette per UI_UX_DESIGN.md §6 unchanged | Current major of the TRD-named stack; smallest config surface | Team |
| 2026-09-09 | Route weights from DGCA DOM city-pair passenger data (July 2026), version WB-2026.09-DGCA; loader `scripts/load_dgca_weights.py`, fixture `data/fixtures/dgca_citypair_weights.json`; placeholder dict kept as fallback | PS 26056: basket "selected on the basis of DGCA passenger-traffic data" — real data now available | Team |
| 2026-09-09 | Backtest reference = MoSPI CPI Airfare sub-index (2024=100, All India Combined, item 294) via eSanklyiki; loaders `collectors/sources/mospi_cpi.py` + `scripts/load_cpi_backtest.py`, offline fixture committed; synthetic fallback retained | PS 26056 demands a 30-day backtest "against publicly available DGCA monthly average-fare data", which research proved was never published — CPI Airfare is the honest official replacement (and the exact component APIx augments) | Team |
| 2026-09-10 | Replay window extended to 379 days (2025-08-25 → 2026-09-07); base period moved to 2025-08-25 → 2025-09-23; methodology version stays APIX-v1.0 on a fresh reseed | The base period must precede the CPI reference window for the backtest to align on all 6 published months (was 2). Formula/weights/basket unchanged; whole DB reseeded so no coexisting series. Live-verified the CPI API returns exactly those 6 months (2024 empty) — 6 is the official ceiling | Team |
| 2026-09-10 | Replay fixture `data/fixtures/replay_quotes.jsonl` untracked from git (gitignored) | 12-month dataset is 96MB — at GitHub's 100MB per-file reject limit; deterministically regenerable from the seeded generator; make.sh already regenerates when missing | Team |
| 2026-09-10 | Scheduled collection = APScheduler per TRD §11 (`scripts/schedule_collect.py`, 08:00 IST cron, idempotent job keys); collect_demo gained real_clock mode | PS "scheduled daily extraction"; TRD names APScheduler as MVP; same-day double-fires dedup via the job key | Team |
| 2026-09-10 | Playwright JS-rendering is an OPTIONAL capability path (`collectors/sources/js_engine.py`) behind the identical compliance gate, demonstrated on the sim portal's `/flights/search-js`; import-guarded so nothing depends on it | PS names the toolchain and "handle JavaScript-rendered pages"; real funnels are JS + anti-bot, so capability + honest BLOCKED statuses is the compliant answer. No stealth/evasion, ever | Team |
| 2026-09-10 | PS-named portals registered `active=False` with frozen research verdicts via `scripts/probe_sources.py` (fixture `data/fixtures/source_probe.json`; `--live` refreshes robots evidence only) | Registry documents WHY each PS-named source is absent (verbatim robots.txt evidence) — absence becomes diligence, never silence; verdicts change only via the research doc | Team |
| 2026-09-10 | Demo retention prune never deletes the methodology base period (floor = base_period_end + 1) | With a 12-month window the old 90-day prune wiped the base period and broke index recomputation — found live, fixed root-cause in `prune_demo_data` | Team |

---

## 9. Open Questions

- [x] Exact official route basket and weight source. RESOLVED 2026-09-09: route weights derive from DGCA DOM city-pair July 2026 passenger data (fixture committed; regenerate via `scripts/load_dgca_weights.py --refetch`). Basket composition itself still follows the 10-route demo basket; a future DGCA traffic-volume-ranked basket would be a methodology change.
- [ ] Exact DGCA historical reference dataset and mapping. RESOLVED (frozen 2026-09-09): DGCA monthly average-fare data does NOT exist publicly (deep research verified). Official backtest reference is instead the MoSPI CPI "Airfare" sub-index (2024=100, All India, Combined, item 294) from eSankhyiki — the exact CPI component APIx augments. Loader `collectors/sources/mospi_cpi.py`, fixture `data/fixtures/cpi_airfare.json`, CLI `scripts/load_cpi_backtest.py` (refresh via `--live`). Co-movement framing only, never equivalence.
- [ ] Final source list permitted for automated collection.
- [ ] Final deployment target.
- [ ] Final authentication provider.
- [ ] Final institutional data-retention requirements.

---

## 10. UI Direction

Design language: **Airspace Observatory** (Air Traffic Control × Economic Observatory). Signature elements: route observatory, Index Pulse, evidence drawer, lead-time curve, data-confidence meter, source-health cockpit, methodology recipe. Full spec: `UI_UX_DESIGN.md`.

---

*Workflow for how AI assistants should use this and the other docs is defined once, in `CLAUDE.md` §1 and §3 — not repeated here.*
