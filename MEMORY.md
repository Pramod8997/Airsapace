# MEMORY — AirStat India · current state · updated 2026-09-30
Purpose: what is true *now*. Reference material lives in ARCHITECTURE.md / PRD.md; don't copy it here. Update after every meaningful session; log detail goes in `log.md`.

## 1. Identity
AirStat India · SIH 2026 · PS 26056 · MoSPI/DIID · Smart Automation · Software.
Pipeline: Observe → Validate → Normalize → Quality-score → Aggregate → Explain → Backtest → Publish.
Strategy (2026-09-30): **win on robustness and interoperability, not on scraping volume** — Source Ladder, chain-linking, CI, explanation, SDMX, MCP.

## 2. Status snapshot (from previous MEMORY, verified 2026-09-10; re-verify before demo)
- Backend WORKING: FastAPI, v1 endpoints, 152 passed / 1 skipped (CPI live opt-in). Auth/RBAC + audit-write **deferred**.
- Frontend WORKING: React 19 + TS + Vite + Tailwind v4 + ECharts + TanStack Query; 11 screens; same-origin dev proxy.
- DB: SQLite dev (`data/airstat.db`), Postgres via `DATABASE_URL`.
- Collectors: FlightSource contract; ethical engine v2 (robots RFC 9309, rate limit, CAPTCHA/Akamai/Cloudflare detection, bounded retry honouring Retry-After); REAL: Alliance Air + Akasa tariff PDFs, Yatra SEO route fares (fixture-backed; `YATRA_LIVE=1` live); optional Playwright path; 9 PS-named portals registered `active=False` with frozen probe verdicts; 24 sources.
- Engine: APIX-v1.0 deterministic Laspeyres, MAD outliers, QS-v1, input-hash fingerprint; aux: FORECAST-v1, ANOMALY-v1, lead-time elasticity.
- Weights: WB-2026.09-DGCA (DGCA city-pair July 2026). Basket: 10 routes × T+1/7/15/30/45.
- Replay: 379 days (2025-08-25 → 2026-09-07), 185k+ obs, **synthetic**; base period 2025-08-25 → 2025-09-23; fixture gitignored (96 MB), regenerable.
- Backtest: vs MoSPI CPI Airfare (2024=100, All-India Combined, item 294, eSankhyiki); n=6 (official ceiling); corr 0.68, MAPE 6.3%; co-movement framing only.
- Scheduling: APScheduler 08:00 IST, idempotent job keys.
- Deployment: **not started**. One-command: `./make.sh` / `make.bat`.

## 3. Known issues / drift
| Issue | Action |
|---|---|
| README stale (30-day/14.6k obs/42 tests/base 2026-06-25/`WB-2026.09-prototype`) vs real state above | TASKS T0.1 |
| Docs named differently (TRD, UI_UX_DESIGN, memory.md) vs new set | TASKS T0.6 |
| No public URL | T1.1 |
| Real-data volume thin; replay is synthetic | Be explicit in every demo; grow real days daily |

## 4. Frozen decisions (carried forward)
- Modular adapters; engine independent of scraping; raw immutable; versioned calculations.
- Dashboard never depends on live scraping.
- Sold-out ≠ 0; missing ≠ 0 (reweight, not impute).
- Ethical collection: robots/ToS, rate-limit, detect CAPTCHA, stop when restricted, never bypass.
- Backtest reference = CPI Airfare item 294; DGCA monthly average fares are **not** publicly published (researched) — never present as DGCA data.
- SQLite dev / Postgres target; no PG-specific SQL; `create_all` until schema stabilises.
- Playwright is optional capability behind the same compliance gate; no stealth ever.
- Design language Airspace Observatory; ui-ux-pro-max only from that brief.
- Demo retention prune never deletes base period.

## 5. New decisions (2026-09-30)
| Decision | Reason |
|---|---|
| Source Ladder S0–S5 with health FSM; BLOCKED is terminal until human review | Turns the scraping problem into the demo headline; keeps R1 |
| Compliance overrides PS wording on CAPTCHA/IP rotation | PS itself demands robots/ToS compliance; state stance explicitly |
| Overlap chain-linking; no overlap ⇒ no link, label PROVISIONAL | Avoids reading an instrument change as inflation |
| APIX-v1.0 stays frozen; Jevons = shadow APIX-v1.1-J; ancillary = APIX-A experimental | Formula transparency without breaking reproducibility |
| Seeded bootstrap CI (B=500, seed = fingerprint prefix) | Uncertainty while staying deterministic |
| LLM/vision only for Field Capture extraction, human-confirmed | Novel collection channel without touching index path |
| Passive browser-extension DOM capture **out of scope** pending legal review | ToS risk |
| Ship SDMX-JSON + MCP server | Matches MoSPI's Feb-2026 eSankhyiki MCP direction and NSO interoperability norms |
| Public deployment is P1 | Evaluators shouldn't need to run anything |

## 6. Research notes (for talking points; verify before quoting)
- MoSPI launched a beta **MCP server** for eSankhyiki (Feb 2026) covering CPI, WPI, IIP, PLFS, ASI, NAS, Environment; endpoint `https://mcp.mospi.gov.in/`.
- MoSPI CPI API exists at `api.mospi.gov.in` (token auth, 30-min token).
- DGCA's Tariff Monitoring Unit monitors fares on select sectors monthly via airline websites (Lok Sabha reply) → S4 target.
- Other SIH26056 repos exist. One reports 1 of 16 portals usable, a portal blocking bots on 15 Sep 2026, and a fallback to a licensed feed with separate segments; another ships SPPI basis, CPI transport nowcast bridge, MoSPI-style press exports. Expect judges to have seen similar. Our edge: failover proof, CI, explanation, SDMX/MCP, Field Capture, CPI item-294 backtest.
- International CPI guidance favours Jevons at elementary level; **confirm MoSPI CPI-2024 method** before claiming alignment.
- PS viewer showed submission deadline 30 Sep 2026 — confirm on sih.gov.in.

## 7. Current sprint
```
Sprint: Submission + robustness story        Start: 2026-09-30   End: open
Objective: P0 (README, deck, video) → P1 (deploy, FSM, linking, ladder cockpit, CI, contributions)
Next action: T0.1 README fix
```

## 8. Blockers / open questions
- [ ] Is 30 Sep the hard deadline for the team's submission? (check portal)
- [ ] Which S1 licensed/aggregator API is acceptable and affordable? (Travelpayouts-style is proven by another team; evaluate others)
- [ ] Extraction provider for Field Capture (API key/cost/offline fallback OCR)
- [ ] Deployment target and free-tier limits
- [ ] Data-retention period for captured images
- [ ] Legal read of portal ToS for enumerator-assisted capture

## 9. How to use (agents)
Read RULES.md → this file → TASKS.md. Work the top unchecked item. Update this file's §2/§5/§7 and `log.md` at end of session.
