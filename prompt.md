# AirStat India — Agent Plugin Setup

Verified against the actual repos on 2026-09-08. All three are real, popular Claude Code plugins/skills — install commands below are copied from their READMEs.

---

## 1. ponytail — anti-overengineering discipline

**What it is:** a Claude Code skill/plugin that makes the agent write the minimum code that satisfies the task (YAGNI ladder: skip → reuse → stdlib → native → existing dep → one-liner → minimum implementation), without cutting validation, error handling, security, or accessibility. Real repo, MIT license: https://github.com/DietrichGebert/ponytail

**Why it fits this project:** `CLAUDE.md` §6 already says "build the smallest correct system first." Ponytail enforces exactly that discipline at the code-generation level — useful for a hackathon build where over-engineering (extra abstraction layers, premature frameworks) eats time you don't have.

**Install (Claude Code):**
```
/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail
```
(Two separate prompts — the install needs both.)

**Usage:** active every session by default (mode `full`). `/ponytail-review` reviews a diff for over-engineering; `/ponytail lite|full|ultra|off` adjusts intensity.

---

## 2. graphify — codebase knowledge graph

**What it is:** a `/graphify` skill that parses the repo (code via tree-sitter AST, docs/PDFs via the assistant's model) into a queryable knowledge graph instead of relying on grep/re-reading files. Real repo, YC-backed: https://github.com/Graphify-Labs/graphify

**Why it fits this project:** this doc set (`PRD.md`, `TRD.md`, `SECURITY.md`, `UI_UX_DESIGN.md`, `memory.md`, `log.md`) is exactly the kind of cross-referenced, multi-file corpus graphify is built for — instead of an agent re-reading all six files to find one fact, it can query the graph. Complements the CLAUDE.md token-optimization work already done: fewer full-file reads, more targeted lookups.

**Install:**
```
uv tool install graphifyy      # or: pipx install graphifyy
graphify install               # registers the skill with Claude Code
```
Then in Claude Code: `/graphify .` — produces `graphify-out/graph.html`, `GRAPH_REPORT.md`, `graph.json`.

**Note:** the PyPI package is `graphifyy` (double-y) — the CLI command is still `graphify`. Add `graph.json` / `graphify-out/` to `.claudeignore` per its own troubleshooting notes, so regenerating the graph doesn't invalidate Claude Code's prompt cache on every turn.

---

## 3. ui-ux-pro-max — design-system generator

**What it is:** a skill that generates a full design system (colors, typography, patterns, anti-patterns, accessibility checklist) from a product description, with stack-specific guidance for 22 frameworks including React/Tailwind. Real repo: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill

**Why this one needs care, not a blind install:** this project already has a complete, opinionated design spec — `UI_UX_DESIGN.md`'s "Airspace Observatory" direction (restrained palette, route observatory, evidence drawers, no generic dashboard aesthetic). A generic design-system generator's default output (industry-matched palettes, landing-page patterns) is built for things like SaaS marketing pages, not a government-analytics cockpit. **If installed, point it at the existing spec rather than letting it invent a new one** — e.g. feed it the Airspace Observatory direction as the brief instead of a generic "airfare dashboard" prompt, or skip its design-system generator entirely and use it only for the accessibility/UX-guideline checks (resilient text, focus states, reduced-motion) which are stack-agnostic and don't conflict with anything in `UI_UX_DESIGN.md`.

**Install (Claude Code):**
```
/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
/plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

---

## Once plugins are installed

1. Record which of the three you actually installed in `memory.md` (Frozen Decisions or Open Questions).
2. Note it in `log.md` under the current dev-log entry.
3. For ui-ux-pro-max specifically: confirm with whoever's driving the UI work whether it's used for design generation or just the accessibility checklist, per the caution above.
