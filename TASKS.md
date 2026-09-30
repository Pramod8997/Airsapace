# TASKS — Prioritised backlog · 2026-09-30
Rule: work top-down. Don't start P2 while a P0/P1 is open. Tick here, then update MEMORY.md and log.md.
Effort: S ≤ 2 h · M ≤ ½ day · L ≤ 1 day. **DoD** = RULES §F.

> ⚠ The SIH problem-statement viewer showed **submission closing 30 Sep 2026** (data captured 4 Sep). Confirm on sih.gov.in whether this is today for *your* idea/PPT submission. If yes, do **P0 only** first — submission artifacts beat new code.

## P0 — Submission-critical (do first, mostly no new code)
- [ ] **T0.1 (S)** Fix README drift: it says 30-day replay / 14.6k obs / 42 tests / base 2026-06-25 / `WB-2026.09-prototype`; MEMORY says 379 days / 185k+ / 152 tests / base 2025-08-25 / `WB-2026.09-DGCA`. Make README match reality. *Judges read README first.*
- [ ] **T0.2 (M)** Idea deck (SIH template): problem → **Source Ladder** → index method → differentiators D1–D10 → honesty → roadmap. One slide "What we do when a site blocks us".
- [ ] **T0.3 (S)** Add repo description + topics; pin screenshots; add "Not official CPI" line.
- [ ] **T0.4 (M)** Record 3-min demo video using PRD §10 script (screen capture of existing UI is enough today).
- [ ] **T0.5 (S)** Add `docs/SCRAPING_STRATEGY.md` (1 page): PS-vs-compliance stance, ladder table, probe evidence table from `source_probe.json`.
- [ ] **T0.6 (S)** Copy these six docs into repo; `git mv memory.md MEMORY.md` (case-insensitive FS: do via temp name); reduce `CLAUDE.md` to pointer; TRD.md gets header "superseded by ARCHITECTURE.md".

## P1 — Must-have wins (next 2–4 days)
- [ ] **T1.1 (L)** Public deployment (one container, free tier, compact seeded DB). **DoD:** URL loads Overview in < 3 s; mode ribbon says REPLAY/DEMO honestly.
- [ ] **T1.2 (M)** Source Health FSM + evidence records (`source_health`), wired to existing engine detections. Tests: 403/CAPTCHA/robots ⇒ no further requests in cool-down (FR-20/21).
- [ ] **T1.3 (M)** Segments + `linking.py` overlap chain-link + `segment_link` table + property test (FR-22).
- [ ] **T1.4 (M)** Pseudo-switch validation script → drift number for Backtest Pack (state the actual, not the target).
- [ ] **T1.5 (M)** `uncertainty.py` seeded bootstrap CI; API + Overview CI band (FR-23/24).
- [ ] **T1.6 (M)** `contribution.py` + endpoint + "Why did it move?" drawer (FR-25).
- [ ] **T1.7 (M)** Sources → Source Ladder Cockpit UI + **Failover Drill** (demo-mode simulation, labelled).
- [ ] **T1.8 (S)** Golden determinism test (fingerprint stable over 3 runs).
- [ ] **T1.9 (M)** API keys + rate limit for read routes; JWT+RBAC for admin (FR-30).
- [ ] **T1.10 (S)** Verify weekly + monthly APIx endpoints/screens exist (PS asks daily/weekly/monthly); add if missing.

## P2 — Differentiators (after P1 green)
- [ ] **T2.1 (M)** `mcp_server/` FastMCP with 5 tools (FR-29); doc + copy-paste config; test with MCP inspector. Demo alongside MoSPI MCP (`https://mcp.mospi.gov.in/`).
- [ ] **T2.2 (M)** SDMX-JSON endpoint + schema validation test (FR-28).
- [ ] **T2.3 (M)** APIX-v1.1-J Jevons shadow + sensitivity chip/panel. **Before claiming alignment, read MoSPI CPI-2024 methodology and cite it.**
- [ ] **T2.4 (L)** Field Capture PWA + `/field/captures` + extraction adapter (provider-swappable) + confirm step + validator + review queue (FR-26/27). Fixture screenshots for tests.
- [ ] **T2.5 (M)** Festival/long-weekend `calendar_event` table + event flags on charts + Backtest #4.
- [ ] **T2.6 (S)** Crawler charter page + declared UA + data-sharing request kit (letters to airlines/OTAs/DGCA-TMU).
- [ ] **T2.7 (M)** Backtest Pack v2 page (5 panels) (FR-31).
- [ ] **T2.8 (S)** S1 licensed-API adapter hardening (Travelpayouts-style) as its own segment; document that it is a search-cache instrument.

## P3 — Stretch
- [ ] T3.1 APIX-A ancillary series from published fare sheets (Akasa PDF first).
- [ ] T3.2 STL seasonal adjustment aux layer.
- [ ] T3.3 S4 ingest stub for DGCA-TMU style CSV.
- [ ] T3.4 Hindi labels for headline strings.
- [ ] T3.5 Alembic migrations once schema stabilises.
- [ ] T3.6 Postgres CI job.

## Demo-readiness gate (all must be ✔ before evaluation)
- [ ] Public URL up · [ ] Failover Drill works offline · [ ] Video backup of demo · [ ] README matches reality · [ ] `./make.sh` works from clean clone · [ ] Suite green · [ ] Every screen shows mode ribbon + version + Q · [ ] One-slide answer to "what if sites block you?" rehearsed · [ ] Honest answer prepared for "how much real data do you have?"

## Suggested order if time is short
T0.1 → T0.2 → T1.1 → T1.2 → T1.3 → T1.7 → T1.5 → T1.6 → T2.1 → (T2.4 only if time remains).
Reason: the failover story (D1+D2) + CI + explanation are the highest signal per hour; MCP is cheap and distinctive; Field Capture is the most novel but the most work.
