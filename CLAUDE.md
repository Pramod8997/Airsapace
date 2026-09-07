# AirStat India — Claude Code Operating Contract

SIH 2026, Problem Statement 26056 (MoSPI/DIID). Real-time Airfare Price Index (APIx) platform.

Pipeline: `Observe → Validate → Normalize → Quality-score → Aggregate → Explain → Backtest → Publish`

This file holds rules and pointers only. Full detail lives in the source-of-truth docs below — **read only the ones relevant to your current task**, not all of them every time.

---

## 1. Where to look

| Need | File |
|---|---|
| Product requirements, user journeys, FRs, acceptance criteria | `PRD.md` |
| Tech stack, architecture, repo layout, DB schema, API contracts, adapter interface | `TRD.md` |
| Auth, threat model, secrets, SSRF/CORS/headers, audit logging | `SECURITY.md` |
| Screen specs, components, design tokens, states | `UI_UX_DESIGN.md` |
| Current frozen decisions, sprint, blockers, open questions | `memory.md` |
| Chronological history of what was actually done | `log.md` |

**Conflict priority:** explicit user request > PRD > TRD > SECURITY > UI/UX > memory (frozen decisions) > log (history). If two docs conflict, say so — don't silently pick one — then record the resolution in `memory.md`.

**Source note:** the SIH PPTX has headings for Technical Approach/Methodology/Architecture/Tech Stack but no populated stack under them. `TRD.md`'s stack is the team's recommendation, not something attributed to the PPTX.

---

## 2. Non-negotiable invariants

These are small enough to keep here; everything else is in the linked docs.

- **Index engine is deterministic.** Never an LLM, opaque model, or unversioned heuristic. AI/ML may assist anomaly detection, forecasting, explanation, source-quality diagnostics — never the official calculation.
  `I_t = [ Σ(w_i × P_i,t / P_i,0) / Σw_i ] × 100` — must be reproducible from the same input snapshot + methodology version + weights.
- **Collection and statistics are separate.** A scraper/adapter never calls `calculate_index()`. Adapters map to the canonical schema (see `TRD.md` §6) and stop there.
- **Raw observations are immutable.** RAW → PROCESSED → INDEX. Never overwrite raw with cleaned values.
- **Version everything that affects a result:** methodology, route basket, weights, processor, adapters, calculation runs.
- **Missing/sold-out ≠ zero.** Availability states: `AVAILABLE, SOLD_OUT, MISSING, INVALID, IMPUTED, REJECTED`. An expensive fare is not automatically an outlier — see `PRD.md` §13 for outlier policy.
- **Ethical collection only:** respect robots.txt/ToS, rate-limit, timeout, bounded retry, detect CAPTCHA, pause on restriction, keep demo/replay data so the dashboard never depends on live scraping. Never bypass CAPTCHA/auth/access controls or rotate infra to evade a block.
- **Statistical honesty:** never claim the prototype is official CPI, that DGCA and APIx are methodologically equivalent, that correlation proves equivalence, or that a forecast is an observed price.
- **No silent architectural changes** to DB engine, API framework, frontend framework, index methodology, route weights, base period, or source-policy behavior — explain the trade-off first if a task seems to require one.

---

## 3. Workflow

1. **Understand** — read only the doc(s) from §1 relevant to the task, plus `memory.md` for current state.
2. **Inspect** the existing implementation before adding new files.
3. **Plan** — files touched, API/DB changes, security impact, tests needed.
4. **Implement** the smallest coherent change.
5. **Test** — targeted first, then broader.
6. **Report**: what changed, files changed, tests run/result, known limitations, security notes, next step.
7. **Update `log.md`** (always) and **`memory.md`** (only if a decision, blocker, architecture, assumption, or completion status actually changed).

Don't update `memory.md` for routine work with no state change — that's what `log.md` is for.

---

## 4. Coding standards (quick)

Prefer: type hints, small functions, dependency injection, explicit error handling (domain errors like `SourcePolicyError`, `ValidationError`, `IndexCalculationError`), structured JSON logs, config via env vars not constants.
Avoid: giant functions, hidden global state, magic constants, broad `except:` swallowing, secrets in code or commits.

Full standards, git workflow, and CI checks: not repeated here — use ordinary good practice; security-relevant specifics are in `SECURITY.md`.

---

## 5. Pre-PR checklist

- [ ] Traced to a PRD requirement; follows TRD design; security reviewed; UI matches spec
- [ ] No secrets committed; input validated; error/empty/loading states handled
- [ ] Unit + relevant integration tests added and passing
- [ ] `memory.md` updated if state changed; `log.md` updated always

## 6. SIH priority order (when time-constrained)

`Canonical data model → cleaning → deterministic index → 30-day replay/backtest → API → dashboard → source adapters → security hardening → advanced analytics`

The statistical pipeline matters more than decorative UI. Build the smallest correct system first, then make it impressive.
