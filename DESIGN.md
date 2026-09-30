# DESIGN — Airspace Observatory v2.0
Extends `UI_UX_DESIGN.md` (palette §6, type, grid **unchanged** — keep as source of truth for tokens). This file adds screens/components for v2 features. Design language: Air Traffic Control × Economic Observatory. Serious, evidence-first, calm.

## 1. Principles
1. **Evidence before ornament.** Any number → click → method, sample, lineage.
2. **Honesty is visible.** Mode ribbon, provisional badges, segment breaks are design elements, not footnotes.
3. **Failure is a feature.** Blocked sources look *handled*, not broken.
4. **Analyst density, glanceable summary.** Overview readable in 5 s; drill-down for the rest.
5. **Accessible:** WCAG AA contrast, keyboard focus states, reduced-motion respected, colour never the only signal (icon + label).

## 2. Global chrome (all screens)
| Element | Behaviour |
|---|---|
| **Mode ribbon** (top) | `LIVE` / `DEMO` / `REPLAY` + data date + "Not official CPI". Always visible |
| **Version chip** | `APIX-v1.0 · BASKET-… · WB-…` click → Methodology |
| **Coverage meter Q** | 0–100% arc; amber < 60% ⇒ PROVISIONAL badge |
| **Segment marker** | Vertical dashed line on charts at source switch; tooltip shows tier, λ, overlap |
| **Lang** | EN + Hindi labels for headline strings (cheap i18n table; optional) |

## 3. Existing 11 screens — v2 changes
| Screen | Change |
|---|---|
| Overview | Add **CI band** on 30-day trend; "Why it moved" card (top 3 contributors, festival flag); Q meter; formula-gap chip (v1.0 vs Jevons) |
| Index | Toggle series: v1.0 / v1.1-J / APIX-A; CI on/off; segment markers |
| Routes | Heatmap unchanged; evidence drawer gains contribution + source mix |
| Sources | Becomes **Source Ladder Cockpit** (§4) |
| Quality | Add capture-review queue count and S3 confirm/reject rates |
| Backtest | Becomes **Backtest Pack v2** (5 panels §5) |
| Methodology | Add Segments & linking section, uncertainty method, spec definition |

## 4. New: Source Ladder Cockpit
```
┌ S0 Tariff PDFs   ● HEALTHY     last good 08:02   coverage 12%
├ S1 Data APIs     ● HEALTHY     last good 08:00   coverage 55%
├ S2 Public pages  ▲ LAYOUT_CHG  repair queued     coverage 0%
├ S3 Field Capture ● ACTIVE      37 today, 4 in review
├ S4 Institutional ○ NOT CONNECTED  [request kit]
└ S5 Replay        ◌ DEMO ONLY
```
- Row expands to evidence (status codes, robots excerpt, detection reason) — verbatim, timestamped.
- State glyphs: ● healthy, ▲ needs repair, ■ blocked (do-not-evade), ◐ outage, ○ n/a. Colour + shape + text.
- **Failover Drill** (demo mode only, clearly labelled SIMULATION): button forces a source to BLOCKED → animated ladder shows freeze → next tier → λ badge → Q dips → trend continues with segment marker. Undo restores.
- **Crawler Charter** link, **Data-sharing request kit** download.

## 5. New: Backtest Pack v2 (single scroll page)
Panels: (1) APIx monthly vs CPI Airfare, n=6 stated, co-movement stats · (2) Pseudo-switch drift chart · (3) CI calibration bar · (4) Event-response small multiples · (5) Determinism hash table (3 runs, identical ✔). Each panel: one-sentence takeaway + "what this does NOT show".

## 6. New: "Why did it move?" drawer
Waterfall of contributions summing to Δ. Tabs: Route · Lead-time · Fare component. Event chips (Diwali, long weekend…). Explicit line: "Contributions are arithmetic decomposition, not causal claims."

## 7. New: Field Capture PWA (mobile-first, 360 px)
Flow, 4 steps, one thumb: **Route+date → Capture photo → Review fields → Submit.**
- Review card: extracted fare, taxes, carrier, times; low-confidence fields outlined amber with "check me".
- Big primary button; offline queue with "will sync" state; success haptic + toast; no PII fields.
- Empty/error states written for humans ("Couldn't read the fare — retake or type it").
- Installable, works on low-end Android; Hindi/English toggle.

## 8. New: API & MCP console
Tabs: REST (Swagger embed), SDMX sample, MCP (tool list + copy-paste config for MoSPI-style clients), API-key request. Shows example prompt: "Compare APIx with CPI airfare for the last 6 months."

## 9. Components
Index Pulse · Confidence meter · Evidence drawer · Lead-time curve · Route heatmap · Ladder row · State badge · Segment marker · Waterfall · CI band · Mode ribbon · Capture card · Provenance link (hash chip). Reuse before creating; no new chart library (ECharts only).

## 10. Motion & states
150–250 ms, ease-out; drill-down transitions only; failover animation ≤ 1.2 s; all disabled under `prefers-reduced-motion`. Every data view has loading skeleton, empty, error-with-retry, and stale-data state.

## 11. Copy tone
Plain, precise, no hype. "Provisional — coverage 52% (< 60%)". "Blocked by source — collection paused, not bypassed."

## 12. Acceptance checklist
Mode ribbon on every screen · Q + version on every figure · colour-blind safe · keyboard reachable · 360 px works · no layout shift on data load · screenshots in `docs/screenshots` refreshed and README updated.
