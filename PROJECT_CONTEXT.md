# Project Context — Smart Email Triage

> Durable map for a **new OpenCode session**. Read this first, then load the
> skills it names. Two rules keep this file useful:
> 1. **This file points at the policy — it never restates it.** The skills are the
>    single source of truth; copying rules here creates drift.
> 2. **Only the `## Status / handoff` section changes often.** Keep the rest stable.

---

## What & why

Build a command-line **"terminal agent"** for the Smart Email Triage challenge:
read a batch of customer emails and write one triage row per email
(`category`, `priority`, `action`, `reply_draft`, `reason`).

**Success looks like:** `python -m agent --input emails.csv --output results.csv`
runs clean, every output row passes enum + `reply_draft` validation, an eval
script reports per-field accuracy, and a short README explains the design.

---

## Source of truth (do NOT duplicate)

Triage decisions **and** the build workflow live in project-local skills. Load
them with the `skill` tool; do not copy their contents into other files.

- **`email-triage-policy`** — the *decisions*: taxonomy, priority/action rule
  tables, reply policy, injection guard.
  References: `.opencode/skills/email-triage-policy/references/{taxonomy,priority-rules,reply-policy}.md`
- **`terminal-triage-agent`** — the *build workflow*: I/O contract, model/code
  split, validation, eval, README.

**Core split — model classifies, code decides:** the model proposes `category` +
a short rationale; **code** derives `priority`, `action`, and `reason` from the
rule tables. Output must be stable and explainable; the model does not freelance
on priority/action.

`AGENTS.md` is the always-loaded rules file (intent → skill mapping).

---

## Architecture (detail lives in `terminal-triage-agent`)

```
read emails.csv
  -> build prompt (embed the policy references)
  -> model call -> JSON {category, rationale, reply_draft?}
  -> validate (schema + enums)
  -> apply priority/action rule table in code
  -> write results.csv + log the decision trail
```

- **A single fixed pipeline — not an agent loop** (no retrieval/tool use here).
- Keep every format detail in one module (`io.py`); if the schema changes, only
  that file changes.
  - input `emails.csv`: `id, sender, subject, body`
  - output `results.csv`: `id, category, priority, action, reply_draft, reason`
  - `reply_draft` is empty **unless** `action == reply`.

---

## Repo map

| Path | Purpose |
| ---- | ------- |
| `AGENTS.md` | Agent rules + intent→skill mapping (always loaded) |
| `opencode.jsonc` | Loads external skills from `~/agent-skills/skills` |
| `PROJECT_CONTEXT.md` | This file — durable map + session handoff |
| `.gitignore` | Ignores secrets/`.env*`, `.opencode/*` (except skills), `__pycache__/`, `out/`, `*.log` |
| `.opencode/skills/email-triage-policy/` | Decision rules (taxonomy, priority/action, reply) |
| `.opencode/skills/terminal-triage-agent/` | Build workflow for the agent |

**Not yet created:** `agent/` package (`io.py`, model wrapper, rules, `__main__.py`),
`emails.csv`, `results.csv`, eval script, README, tests.

---

## Decisions log (append-only)

- **2026-10-11** — Adopted a single `PROJECT_CONTEXT.md` (stable map + status)
  rather than a two-file split; revisit if the status section grows.
- **OPEN** — Model provider/API for the classification call (e.g. Anthropic /
  OpenAI / local) is **undecided**. Config must come from env vars; no secrets
  in the repo.
- **OPEN** — No sample `emails.csv` exists yet; may seed from a 3-row fixture.

---

## Status / handoff  ← update this section every session

- **State:** scaffolding only. Committed as `f3c35b1` ("Add email triage
  challenge: skills, policy refs, AGENTS.md, config, and selective
  .gitignore"). **No agent code exists yet.**
- **Repo:** branch `master`, remote `origin`
  (`github.com/aashutosh-yadav/email-triage-agent.git`).
- **Done so far:** challenge skills scaffolded and committed; `AGENTS.md`,
  `opencode.jsonc`, `.gitignore` in place; initial context exploration complete.
- **Next pending task (per `terminal-triage-agent` order of work):**
  1. End-to-end **stub** on a 3-row fixture (no model call) — get the shape right.
  2. Model wrapper (JSON, retry, typed error).
  3. Validation/repair (never crash on one bad row).
  4. Deterministic priority/action rules.
  5. Eval script **before** tuning.
  6. README.
- **Blocked on:** the model-provider decision + a sample `emails.csv` (or a
  3-row fixture we create ourselves).
- **Working tree:** clean except `PROJECT_CONTEXT.md` (this file, untracked).
  Committing is not yet authorized.

*New session: before acting, read `AGENTS.md`, this status section, and run
`git status` to confirm the actual working-tree state. Re-run verification if
the recorded baseline is missing or the code has moved.*

---

## Verification

- **Run:** `python -m agent --input emails.csv --output results.csv`
- **Invariants that must hold:**
  - `category` ∈ {`billing`, `bug_report`, `feature_request`, `spam`, `other`}
  - `reply_draft` is non-empty **iff** `action == reply`
  - a spam email never produces a reply or an escalation
  - every `priority`/`action` is traceable to a rule table
- **Eval:** `<eval command — not yet created>` — must print per-field accuracy and be reproducible.
- **Repo state:** `git status`

---

## Open questions / risks

- Model provider + API-key handling (env-var config; nothing secret committed).
- Prompt-injection handling must be exercised with adversarial test emails.
- No `emails.csv` fixture yet — need to create one to run anything end-to-end.
