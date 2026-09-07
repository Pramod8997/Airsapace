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
Collectors: SKELETON — FlightSource contract + canonical models exist; 5 synthetic demo sources; no live adapters yet
Statistical Engine: WORKING — APIX-v1.0 deterministic Laspeyres, MAD outliers, QS-v1 quality, versioned + input-hash fingerprinted
Backtesting: WORKING — vs SYNTHETIC reference (labeled, not DGCA); real DGCA series pending
Security: PARTIAL — headers, rate limit, validation, CORS allowlist; auth/RBAC/audit-write deferred
Testing: PASSING — .venv/bin/python -m pytest backend/tests -q → 42 passed; frontend: npx tsc -b && npm run build → clean
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
- Backtest reference series is synthetic and labeled as such everywhere — never present it as DGCA data.

**Agent Tooling** (2026-09-08)
- Claude Code plugins installed (user scope, this machine only — teammates install separately, commands in `prompt.md`): `ponytail` v4.9.0 (anti-overengineering discipline; active by default, mode `full`), `ui-ux-pro-max` v2.13.0.
- `graphify` (CLI 0.8.35 + skill) was already installed — nothing to install. Knowledge graph **not yet built**; run `/graphify .` when first needed. Its outputs (`graphify-out/`, `graph.json`) are kept out of agent context via `.claudeignore`.
- ui-ux-pro-max may generate design **only** when fed the Airspace Observatory direction (`UI_UX_DESIGN.md`) as the brief — never a generic "airfare dashboard" prompt. Its stack-agnostic accessibility/UX checks (resilient text, focus states, reduced-motion) are unrestricted.

---

## 5. Current Sprint

```text
Sprint: Backend core → dashboard
Start: 2026-09-08
End: (open)

Primary objective: smallest correct system per CLAUDE.md §6, then make it impressive.

Tasks:
- [x] Canonical data model + cleaning + deterministic index + replay + backtest + API (2026-09-08, see log.md)
- [x] React dashboard consuming the API (Airspace Observatory, 9 screens) (2026-09-08, see log.md)
- [ ] First live source adapters + APScheduler behind FlightSource contract
- [ ] Auth (JWT + RBAC) before any write/admin endpoint
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

---

## 9. Open Questions

- [ ] Exact official route basket and weight source.
- [ ] Exact DGCA historical reference dataset and mapping.
- [ ] Final source list permitted for automated collection.
- [ ] Final deployment target.
- [ ] Final authentication provider.
- [ ] Final institutional data-retention requirements.

---

## 10. UI Direction

Design language: **Airspace Observatory** (Air Traffic Control × Economic Observatory). Signature elements: route observatory, Index Pulse, evidence drawer, lead-time curve, data-confidence meter, source-health cockpit, methodology recipe. Full spec: `UI_UX_DESIGN.md`.

---

*Workflow for how AI assistants should use this and the other docs is defined once, in `CLAUDE.md` §1 and §3 — not repeated here.*
