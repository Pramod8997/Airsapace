# PRD — AirStat India (APIx) · v2.0 · 2026-09-30
SIH 2026 · PS **SIH26056** · MoSPI / DIID · Supersedes PRD v1. Companion docs: ARCHITECTURE, RULES, DESIGN, TASKS, MEMORY.

## 1. Thesis (one paragraph)
CPI airfare is collected by hand. Airfares move hourly. Every team will "scrape and index". **AirStat wins on what happens when scraping fails**: a *Source Ladder* that degrades gracefully, never evades access controls, chain-links across instrument changes, and publishes every figure with uncertainty, coverage and lineage — exposed to MoSPI/RBI through REST, SDMX and an MCP server that sits beside MoSPI's own eSankhyiki MCP.

**Tagline:** *"An airfare index that survives being blocked — and proves it."*

## 2. Problem
- Manual price collection from limited outlets; >90% of domestic tickets are sold online (PS).
- Portals block bots (robots.txt, Akamai/Cloudflare, CAPTCHA). Other teams report only 1 of 16 portals usable. A scraper-only design is a single point of failure.
- PS lists CAPTCHA/IP-rotation handling **and** robots/ToS compliance. Where they conflict, **compliance wins** (RULES R1). We meet the intent (continuity of collection) by other legitimate channels.

## 3. Users
| User | Need | Success |
|---|---|---|
| NSO price statisticians | Trustworthy, documented series; CPI-comparable | Reproduces any figure from micro-data |
| RBI / policy analysts | Early signal on transport inflation | Nowcast + explanation of moves |
| MoSPI field enumerators | Faster, less error-prone collection | Capture a fare in < 20 s |
| Judges / auditors | Evidence, honesty, robustness | See failover live |

## 4. PS traceability
| PS requirement | Our answer | Status |
|---|---|---|
| Collect from 5 airlines + OTAs | Source Ladder S0–S4 with published coverage matrix | Partial → improve |
| JS pages / CAPTCHA / anti-bot / sessions | Playwright path; detect-and-pause; human capture (S3) instead of solving | Done + S3 new |
| DGCA-based basket, T+1/7/15/30/45 | WB-2026.09-DGCA, 10 routes × 5 windows | Done |
| Clean: outliers, missing, sold-out, fare split | MAD, availability states, decomposition | Done |
| Daily/weekly/monthly APIx | Verify weekly + monthly endpoints exist | Verify |
| Dashboard: trends, heatmap, lead-time elasticity | 11 screens | Done |
| API for NSO/RBI | REST + **SDMX-JSON + MCP + API keys** | Partial → new |
| Docs, tests, 30-day backtest | 152 tests; CPI Airfare (item 294) n=6; **Backtest Pack v2** | Extend |

## 5. Beyond the brief (differentiators) — priority order
| ID | Feature | Why judges care |
|---|---|---|
| D1 | **Source Ladder + Failover Drill** (chaos button in demo) | Turns the scraping problem into the headline |
| D2 | **Overlap chain-linking** across source switches + pseudo-switch validation | Statistically correct answer to "source changed" |
| D3 | **Field Capture PWA** for enumerators/volunteers: screenshot → extraction → human confirm → validated record | Digitises MoSPI's *existing* collection; no bot detection; scalable |
| D4 | **MCP server for APIx** (+ works with MoSPI MCP) | Matches MoSPI's Feb-2026 "AI-ready statistics" direction |
| D5 | **SDMX-JSON export** | Interoperability standard NSOs/IMF use |
| D6 | **Uncertainty**: seeded bootstrap CI on every figure | Statistical maturity |
| D7 | **"Why did it move?"** exact contribution decomposition (route × lead-time × fare component) + festival/event flags | Explainability without ML in the number |
| D8 | **Dual index**: APIX-v1.0 Laspeyres (frozen, official) + APIX-v1.1-J Jevons shadow + formula-sensitivity panel | Formula choice is transparent, not hidden |
| D9 | **APIX-A** experimental ancillary-inclusive series (bags/seat) from published fare sheets | Unbundling is a real CPI measurement problem |
| D10 | **Crawler charter page + data-sharing request kit** (declared user-agent, contact, rate policy; template letters to airlines/OTAs/DGCA-TMU) | Ethical, and opens the S4 policy path |

DGCA's Tariff Monitoring Unit already monitors fares on select sectors monthly from airline websites (Lok Sabha reply) — a MoSPI–DGCA sharing arrangement is the natural long-term source (S4).

## 6. Functional requirements (new/changed only; v1 FR-1…FR-16 stand)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-20 | Each source has a state: HEALTHY / LAYOUT_CHANGED / BLOCKED / OUTAGE / POLICY_DISALLOWED | `/api/v1/sources` returns state + evidence + last-good time |
| FR-21 | BLOCKED or POLICY_DISALLOWED sources are never retried aggressively and never evaded | Test: 403/CAPTCHA fixture → zero further requests within cool-down |
| FR-22 | On segment change, engine links series using overlap ≥ 7 days; publishes link factor + segment id | Test: synthetic switch, linked series within tolerance of truth |
| FR-23 | Every published figure has `ci_low/ci_high`, coverage Q, methodology + basket + weight versions, data mode, input fingerprint | Schema test; UI shows all |
| FR-24 | Bootstrap CI deterministic (seed = input fingerprint) | Two runs → identical CI |
| FR-25 | `/index/{id}/contributions?date=` returns additive contributions summing to Δ (±1e-9) | Property test |
| FR-26 | Field Capture: submit → extract → user confirms → validate → store with `source=FIELD_CAPTURE`, capturer id (pseudonymous) | E2E test with fixture screenshots |
| FR-27 | Extraction output can never reach the index unvalidated; low confidence → review queue | Unit test |
| FR-28 | `GET /api/v1/sdmx/data` returns valid SDMX-JSON for national + route series | Validates against schema |
| FR-29 | MCP server tools: `get_latest_index`, `get_history`, `explain_move`, `get_methodology`, `get_source_health` | MCP inspector smoke test |
| FR-30 | Read-only API keys with rate limit; admin endpoints behind JWT+RBAC | Auth tests |
| FR-31 | Backtest Pack v2 (see §7) auto-generated as a report page | Page renders from stored runs |

## 7. Backtest Pack v2 (honest evidence)
1. **Official co-movement**: APIx monthly mean vs MoSPI CPI Airfare (item 294, All-India Combined). n = 6 is the official ceiling — state it. Report correlation, MAPE, trend-direction; **no equivalence claim**.
2. **Pseudo-switch test**: hide source X mid-window, link to source Y, compare with uninterrupted series → drift in index points.
3. **CI calibration**: fraction of held-out days inside CI.
4. **Event response**: index reaction around festival/long-weekend dates vs non-event baseline.
5. **Determinism**: same inputs → identical hash across 3 runs.
Replay data is **synthetic**; tests 2–4 on replay prove mechanics, not reality. Repeat on real collected days as they accumulate and label which is which.

## 8. Non-goals & honesty
Not official CPI; not a price-comparison app; forecasts never shown as observed; no LLM/ML in the official number; no bypass of any access control.

## 9. Success metrics
Determinism 100%; API p95 < 300 ms; failover drift ≤ 0.5 index pt (target — measure, then state actual); coverage Q reported daily; ≥ 3 tiers demonstrated live; public URL reachable during evaluation.

## 10. Three-minute demo
1. (20 s) Overview: APIx, CI band, data-mode ribbon, Q meter.
2. (40 s) Sources cockpit: ladder, honest coverage matrix. Press **Failover Drill**: portal → BLOCKED, freeze, tier switch, link factor shown, Q dips, index continuous.
3. (30 s) "Why did it move?" waterfall + festival flag.
4. (30 s) Field Capture on phone: photo → confirmed record appears in feed.
5. (30 s) Analyst asks an AI assistant (MCP): "APIx vs CPI airfare last 6 months?"
6. (30 s) Methodology + lineage: click a number → micro-data → hash.

## 11. Risks
| Risk | Mitigation |
|---|---|
| Too little real data | Lead with method + failover + honest labels; grow real days daily; never present replay as real |
| Scope creep before evaluation | TASKS priority gates; D1, D2, D6 first |
| Legal grey areas (S3 extension-style capture) | Ship screenshot + human-confirm only; passive DOM capture is out of scope pending legal review |
| README/doc drift | RULES R12 doc-sync check |
