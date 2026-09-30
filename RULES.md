# RULES — Operating Contract · v2.0
For humans and AI agents. Replaces the rules section of `CLAUDE.md`. Keep `CLAUDE.md` as a 5-line pointer: `Read RULES.md, MEMORY.md, TASKS.md first. Then ARCHITECTURE.md/PRD.md/DESIGN.md as needed.`

## A. Hard rules (never break)
| # | Rule |
|---|---|
| R1 | **Never bypass an access control.** No CAPTCHA solving, proxy/IP rotation to evade blocks, stealth fingerprints, credential abuse, or robots/ToS violation. Where the PS wording conflicts, compliance wins. BLOCKED/POLICY sources stop until a human reviews. |
| R2 | The **official number is deterministic**. No LLM, ML, or unseeded randomness in `statistical_engine` official paths. |
| R3 | **Raw observations are immutable.** Correct by adding, flagging or superseding, never editing/deleting. |
| R4 | **Never fabricate data.** Missing ≠ 0. Sold-out ≠ 0. Replay is synthetic and must always show mode REPLAY/DEMO. |
| R5 | **Formula/weights/basket/spec change ⇒ new version id + changelog.** `APIX-v1.0` is frozen. |
| R6 | **No equivalence claims** between APIx and CPI/DGCA. Co-movement language only. Not official CPI, everywhere. |
| R7 | LLM/vision allowed **only** in Field Capture extraction: confidence-gated, human-confirmed, schema-validated, outside the index path. |
| R8 | Forecasts/anomaly outputs are labelled and never displayed as observed values. |
| R9 | **Every displayed number** shows version ids, data mode, data date, coverage Q, CI (where defined) and links to evidence. |
| R10 | No secrets in git. `.env.example` only. |

## B. Engineering rules
- R11 **Smallest correct change.** No abstractions without a second use. No new dependency without a one-line justification in the log.
- R12 **Doc sync:** any behaviour change updates the matching doc in the same commit (README numbers included — README currently drifts from MEMORY; fix first). Reference, don't copy: facts live in one place.
- R13 **Tests first for statistics.** Property tests for invariants (weights, contributions, linking). Golden file for determinism. Suite must pass before commit: `pytest backend/tests -q` and `npx tsc -b && npm run build`.
- R14 Python 3.10+ compatible; no Postgres-specific SQL; Pydantic v2 at all boundaries.
- R15 Collectors emit canonical schema only. They never import `statistical_engine`.
- R16 Source states change only through the health FSM, with stored evidence.
- R17 Every source registered with an honest `policy_status` and verbatim evidence; absence is documented diligence.
- R18 Conventional commits (`feat|fix|docs|test|chore(scope): …`). One concern per commit. Never commit generated fixtures > 50 MB.

## C. Agent workflow (token-efficient)
1. Read `MEMORY.md` → `TASKS.md` (pick top unchecked P-item). Do not read the whole repo; use `graphify`/grep and open only touched files. Respect `.claudeignore`.
2. State a 3-line plan (files, tests, done-when). Implement. Run only relevant tests, then the full suite once.
3. Update `TASKS.md` (tick), `MEMORY.md` (state/decisions), `log.md` (entry). Stop.
4. Don't refactor unrelated code, restyle, or add features not in TASKS. Ask when a rule conflicts with a task.
5. Prefer deleting code over adding it. `ponytail` discipline stays on.

## D. Statistical conventions
- Price basis: consumer-payable total; also store base/taxes/UDF/convenience fees.
- Base period per methodology record; base-period rows are never pruned.
- Minimum observations per cell and coverage threshold live in config with version; below threshold ⇒ PROVISIONAL, not interpolated.
- Chain-link only with overlap ≥ 7 days; otherwise break and label.
- Bootstrap: B = 500, seed = fingerprint prefix.

## E. Ethical collection checklist (per adapter, before merge)
robots.txt gate (RFC 9309 longest-match) ✔ · declared UA with contact ✔ · rate limit + timeout + bounded retry honouring `Retry-After` ✔ · CAPTCHA/bot-manager detection ⇒ pause + state change ✔ · ToS reviewed and noted ✔ · fixture-backed tests ✔.

## F. Definition of Done
Tests pass · docs synced · no rule violated · version ids updated if numbers changed · UI shows mode/version/Q · log entry written.

## G. Communication style (agents)
Concise. Lead with result. No restating the task. Diffs over full files. Flag uncertainty and unverified claims explicitly (e.g. "verify MoSPI method").
