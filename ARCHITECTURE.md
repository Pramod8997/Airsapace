# ARCHITECTURE — AirStat India · v2.0 · 2026-09-30
Supersedes `TRD.md` (keep TRD for schema/API detail until merged; this file wins on conflict). Additions are marked **NEW**.

## 1. Principles
1. **Collection never computes statistics; the engine never touches the network.**
2. **Raw is immutable.** RAW → PROCESSED → INDEX; nothing overwritten.
3. **Deterministic official number.** Same snapshot + versions + weights ⇒ same series and same hash. No LLM/ML/randomness (except *seeded* bootstrap, seed = input fingerprint).
4. **Compliance is a hard gate, not a preference.** Blocked ≠ retry ≠ evade.
5. **Instrument changes are modelled, not hidden.** Every value belongs to a *segment*.
6. **Demo never depends on live sources.**

## 2. System view
```
 S0 Published tariffs  S1 Licensed/aggregator APIs  S2 Robots-allowed pages
 S3 Field Capture PWA (NEW)   S4 Institutional feeds (DGCA-TMU/airline MoU, NEW path)   S5 Replay (demo only)
        \                |                 |                 /
         v               v                 v                v
   ┌────────────────── Source Ladder Controller (NEW) ──────────────────┐
   │ per-source health FSM · policy gate · cool-down · failover order  │
   └───────────────────────────────┬────────────────────────────────────┘
                                   v  canonical schema (Pydantic)
                    Raw Observation Store (immutable, hashed)
                                   v
              Validate → Normalize → Quality-score → Outlier flag
                                   v
        Segment Builder (NEW): one segment per source-instrument
                                   v
  Statistical Engine: APIX-v1.0 (frozen) · APIX-v1.1-J shadow (NEW) · APIX-A (NEW, experimental)
     + linking.py (NEW) + uncertainty.py (NEW) + contribution.py (NEW) + seasonal.py (NEW, aux only)
                                   v
   REST /api/v1 · SDMX-JSON (NEW) · MCP server (NEW) · CSV · Dashboard · Backtest Pack v2
```

## 3. Source Ladder (answer to "sites block us")
| Tier | Source type | Method | Instrument | Notes |
|---|---|---|---|---|
| S0 | Published tariff/fare PDFs (Alliance Air, Akasa) | fetch + parse | tariff sheet | exists |
| S1 | Licensed / aggregator data APIs (e.g. Travelpayouts/Aviasales Data API — used by another SIH team; evaluate others) | API client | **search cache, one-way cheapest** | Different instrument → own segment |
| S2 | Robots-allowed public pages (Yatra SEO route fares) | httpx / optional Playwright | listing | exists |
| S3 | **Field Capture**: human opens the portal normally, captures screenshot; extraction proposes fields; human confirms | PWA + extraction service | consumer-visible fare | No automation of any portal; mirrors today's manual CPI collection |
| S4 | Institutional data-sharing (DGCA Tariff Monitoring Unit, airline/OTA MoU) | file/API ingest | official | Policy path; ship the request kit + ingest stub |
| S5 | Replay | seeded generator | synthetic | Always labelled DEMO/REPLAY |

**Health FSM per source:** `HEALTHY → LAYOUT_CHANGED | BLOCKED | OUTAGE | POLICY_DISALLOWED`.
- Classify by evidence: 403/429 + bot-manager headers/CAPTCHA/robots ⇒ BLOCKED/POLICY (**terminal until human review**); page loads but zero fare rows ⇒ LAYOUT_CHANGED (repair queue); 5xx/timeouts ⇒ OUTAGE (backoff probe ≤ 1/h).
- Never route a BLOCKED source to any auto-repair. Write a repair/escalation record with evidence.
- Ladder picks the next available tier for the affected cells; index publishes with Q reduced and segment id changed.
- **Crawler charter** (`/crawler` page + declared `User-Agent` with contact URL): rate, hours, robots policy, opt-out address.

## 4. Segments and chain-linking
A *segment* = (source-instrument, reference period). Segments never get spliced by assumption.
- **Overlap method:** with overlap set O (≥ 7 days, ≥ 60% cell coverage), link factor `λ = exp( mean_{t∈O} [ ln I_old(t) − ln I_new(t) ] )`; publish `I_new*(t) = λ · I_new(t)` after the switch. Store λ, O, and both segments.
- **No overlap ⇒ no link:** trend line breaks, headline names its segment, figure flagged PROVISIONAL.
- **Pseudo-switch validation:** hold out a source mid-window, link to another, report drift vs truth (Backtest Pack v2 #2).
- Segments are stored; recomputation from raw reproduces λ.

## 5. Index families (all versioned, all reproducible)
| Version | Formula | Role |
|---|---|---|
| **APIX-v1.0** | `I_t = 100·Σ wᵢ(Pᵢₜ/Pᵢ₀)/Σ wᵢ` (spec i = route × lead-time) | **Official, frozen.** Do not change; new methods get new versions |
| **APIX-v1.1-J** (shadow) | `I_t = 100·exp(Σ wᵢ ln(Pᵢₜ/Pᵢ₀)/Σ wᵢ)` | Elementary-aggregate Jevons, per international CPI Manual guidance; verify MoSPI CPI-2024 method before claiming alignment |
| **APIX-A** (experimental) | as v1.0 on price incl. published ancillary charges | Unbundling effect; only where charges are published |
- **Sensitivity panel:** v1.0 vs v1.1-J gap by day (formula-choice risk shown, not hidden).
- **Spec (quality-adjustment) definition:** economy · 1 adult · one-way · cheapest nonstop · no add-ons · fixed departure-time band; changes to spec ⇒ new basket version.
- **Missing** ⇒ reweight (drop from num+denom). **Sold-out ≠ 0.** Flag outliers, never delete.

## 6. Uncertainty, explanation, seasonality (all outside the point estimate's determinism)
- **`uncertainty.py`:** within-cell bootstrap of observations, B = 500, seed = first 8 bytes of input fingerprint ⇒ deterministic 95% CI per day/route.
- **`contribution.py`:** exact additive contributions. Laspeyres: `cᵢ = 100·wᵢ(Pᵢₜ/Pᵢ₀ − Pᵢₜ₋₁/Pᵢ₀)/Σw` so `Σcᵢ = I_t − I_{t−1}`. Jevons: log-contributions. Group by route, lead-time, fare component (base / taxes / fees).
- **`seasonal.py`:** festival/long-weekend calendar flags + STL seasonal adjustment. Auxiliary only; labelled; never replaces the headline. DGCA itself names season, holidays, festivals, long weekends, events, competition, rupee and ATF as fare drivers → these are the flag categories.
- Forecast (FORECAST-v1) and anomaly (ANOMALY-v1) stay read-only aux layers.

## 7. Field Capture (S3) — design
```
PWA (mobile) → POST /field/captures (image, route, date, portal) 
   → extraction service (vision/OCR; provider-swappable; stateless)
   → proposed fields + per-field confidence
   → PWA shows editable card → human confirms
   → validator (schema, plausibility band, fare-component consistency, duplicate key)
   → RAW store with source=FIELD_CAPTURE, pseudonymous capturer id, image hash (image itself retained N days then purged)
```
- LLM/vision is **extraction only**, confidence-gated, human-confirmed, validated. It is outside the index path.
- Privacy: no passenger PII requested; strip EXIF/location; DPDP-aligned retention config.
- Anti-gaming: per-capturer rate/plausibility stats, duplicate detection, outlier reputation score.

## 8. Interfaces
| Interface | Detail |
|---|---|
| REST `/api/v1` | v1 endpoints unchanged. **NEW:** `/index/{id}/contributions`, `/segments`, `/sources/{id}/health`, `/backtests/pack`, `/field/captures` |
| **SDMX-JSON** | `/api/v1/sdmx/data?flow=APIX&key=...` minimal data message: dims = FREQ, ROUTE, LEADTIME, INDEX_VERSION; attrs = CI, Q, MODE |
| **MCP** (`mcp_server/`, FastMCP, HTTP) | tools: `get_latest_index`, `get_history`, `explain_move`, `get_methodology`, `get_source_health`; read-only; same auth as REST |
| Auth | Read-only API keys + rate limit; JWT + RBAC for admin/field roles |
| Export | CSV (exists), SDMX, OpenAPI |

## 9. Data model additions (SQLAlchemy; no PG-specific SQL)
`source_health(source_id, state, evidence_json, since, last_good)` ·
`segment(id, source_id, instrument, ref_start, ref_end, status)` ·
`segment_link(id, from_seg, to_seg, overlap_start, overlap_end, lambda, n_cells)` ·
`index_point(…existing…, ci_low, ci_high, q, segment_id, mode, fingerprint)` ·
`field_capture(id, capturer_pseudo, image_sha256, proposed_json, confirmed_json, status, created_at)` ·
`calendar_event(date, kind, label)` · `api_key(id, hash, role, rate_limit)`.

## 10. Determinism contract
`fingerprint = SHA-256(sorted input observation hashes ‖ methodology ver ‖ basket ver ‖ weight ver ‖ segment/link ids)`. Golden-file test: fixed fixture ⇒ fixed fingerprint and series. Any change to numbers requires a version bump + changelog entry.

## 11. Deployment
- Single container (API + built frontend static) + scheduler; SQLite → Postgres via `DATABASE_URL`.
- Free-tier host for a **public URL** (evaluators should not need to run anything). Startup seeds a *compact* replay DB (the 96 MB fixture stays gitignored; ship a small generated DB or generate on boot).
- Cron/APScheduler daily 08:00 IST (exists) + hourly source-health probe.
- Secrets in env only; `.env.example` maintained.

## 12. Security (delta to SECURITY.md)
Auth on all non-public routes; image upload limits/MIME sniffing/AV-safe storage; SSRF allowlist for collectors (exists); audit log for confirm/reject actions; no secrets in fixtures.

## 13. Test strategy
Golden determinism · property tests (contribution sums, weight invariance) · FSM transition tests · chain-link recovery test · CI determinism · SDMX schema validation · MCP smoke · Field Capture E2E on fixtures · compliance tests (403/CAPTCHA/robots ⇒ no further requests) · existing 152 stay green.
