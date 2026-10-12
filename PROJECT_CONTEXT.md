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

**Success looks like:** `python3 agent.py --input emails.csv --output results.csv`
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
- Format details live in `agent.py`; if the schema changes, that file is where
  the change lands.
  - input `emails.csv`: `id, sender, subject, body`
  - output `results.csv`: `id, category, priority, action, reply_draft, reason`
  - `reply_draft` is empty **unless** `action == reply`.

---

## Repo map

| Path | Purpose |
| ---- | ------- |
| `AGENTS.md` | Agent rules + intent→skill mapping (always loaded) |
| `opencode.jsonc` | Loads project-local skills from `.opencode/skills` (portable; external pack optional) |
| `PROJECT_CONTEXT.md` | This file — durable map + session handoff |
| `.gitignore` | Ignores secrets/`.env*`, `.opencode/*` (except skills), `__pycache__/`, `out/`, `*.log`, `*.zip` |
| `.opencode/skills/email-triage-policy/` | Decision rules (taxonomy, priority/action, reply) |
| `.opencode/skills/terminal-triage-agent/` | Build workflow for the agent |
| `agent.py` | **Single entry point**: I/O, rule layer (regexes + decision table), pydantic-validated LLM wiring, validation, CLI |
| `agent_llm.py` | Groq wrapper: delimited untrusted-data prompt, temp 0, `CategoryProposal` pydantic model, retry-once, typed `GroqError`; default model `openai/gpt-oss-20b` |
| `eval.py` | Scores predictions vs a labeled CSV (`--cases`); prints per-field + escalation-row accuracy and every mismatch |
| `eval_cases.csv` | 36 **tuned** labeled emails (normal / injection / non-English / empty / long / ambiguous / spam-bait) |
| `heldout_cases*.csv` | Held-out sets (26/20/16 rows), authored from the policy — **measure, do not tune** |
| `test_rules.py` | 39 stdlib `unittest` rule-layer tests |
| `test_llm.py` | 14 stdlib `unittest` LLM wiring tests (retry/fallback/validation, mocked HTTP) |
| `emails.csv` / `results.csv` | Sample input / regenerated output |
| `requirements.txt` | `pydantic`, `requests` (only) |
| `.env.example` | `GROQ_API_KEY`, `GROQ_MODEL` |

The former `agent/` package (io/rules/model/`__main__.py`) was **deleted** — it
shadowed `agent.py` on `import agent` and duplicated the entry point.

---

## Decisions log (append-only)

- **2026-10-11** — Adopted a single `PROJECT_CONTEXT.md` (stable map + status)
  rather than a two-file split; revisit if the status section grows.
- **2026-10-12** — Model provider fixed: **Groq** via `agent_llm.GroqClient`
  (`GROQ_API_KEY`, `GROQ_MODEL` env vars; free-form LLM category validated by a
  pydantic `Literal` model). Deterministic safety layer stays in code.
- **2026-10-12** — Force-escalation rules run **before** the spam shortcut;
  per-rule priority (refund/angry/empty → `medium`, injection/legal/breach/
  outage/... → `high`); spam needs ≥2 distinct signals ("earnings" removed).
- **2026-10-12** — Single entry point: deleted the `agent/` package; `agent.py`
  owns everything. Decision trail goes to an append-only JSON log
  (`--log`, default `out/decision_log.jsonl`), **not** into `results.csv`.
- **2026-10-12** — LLM `spam` is **distrusted unless the regex detector agrees**
  (else fall back to the regex category, logged as `llm_spam_rejected`); the CLI
  warns explicitly when the LLM is unavailable. Groq default model moved to
  `openai/gpt-oss-20b` after `llama-3.1-8b-instant` was retired 2026-08-16.
- **2026-10-12** — Kept a **held-out** eval set (authored from the policy, never
  tuned) to measure generalization honestly; `heldout_cases*.csv`. The tuned
  `eval_cases.csv` 100% is expected to be optimistic.

---

## Status / handoff  ← update this section every session

- **State:** the agent is **fully built and green**. `python3 agent.py`
  (LLM-first) + `python3 agent.py --no-llm` (deterministic) both run clean; the
  tuned eval scores **category 100% / priority 100% / action 100% /
  action-on-escalation 100%** on `eval_cases.csv` (36 rows); 53/53 tests pass
  (`python3 -m unittest discover -s . -p 'test_*.py'`). Held-out sets measure
  **#1 73.1/96.2/88.5**, **#2 80/85/85**, **#3 100/100/100**.
- **Repo:** branch `master`, remote `origin`
  (`github.com/aashutosh-yadav/email-triage-agent.git`). Recent commits:
  `c1a2178` (Step F/final), `32a271d` (review fixes), `023f123` (eval+tests),
  `edd89a1` (delete agent/ package), `0cfffb9` (LLM wiring), `785aa78`
  (rule hardening).
- **Done:** rule hardening (escalation-before-spam, injection + outage,
  numbers-based refund threshold, spam ≥2 signals); model spam distrusted
  unless regex agrees; explicit LLM-unavailable warnings; Groq LLM wiring
  (pydantic, retry once, temp 0, delimited prompt, regex fallback, `--no-llm`,
  decision log); single entry point; tuned + held-out eval sets; tests; README;
  `.env.example` (default `openai/gpt-oss-20b`); `requirements.txt` trimmed.
- **Next:** none required. Optional: live Groq smoke test with a real key
  (`python3 eval.py --llm`), re-run on a fresh clone, broaden non-English spam/bug
  coverage.
- **Known issues:** real Groq call never exercised here (no `GROQ_API_KEY` in
  this env — mock-tested instead); non-English coverage beyond French is partial;
  single-signal spam intentionally falls through (documented in README).
- **Working tree:** should be clean after the latest commit.

*New session: before acting, read `AGENTS.md`, this status section, and run
`git status` to confirm the actual working-tree state. Re-run verification if
the recorded baseline is missing or the code has moved.*

---

## Verification

- **Run:** `python3 agent.py --input emails.csv --output results.csv`
  (add `--no-llm` for a deterministic, key-free run)
- **Invariants that must hold:**
  - `category` ∈ {`billing`, `bug_report`, `feature_request`, `spam`, `other`}
  - `reply_draft` is non-empty **iff** `action == reply`
  - spam never produces a reply or an escalation, **but** forced-escalation
    signals (incl. prompt injection) are checked *before* the spam shortcut
  - every `priority`/`action` is traceable to a rule table
- **Eval:** `python3 eval.py` — prints per-field accuracy, action accuracy on
  escalation rows, reply_draft invariant violations, and every mismatching row.
  Baseline (2026-10-12): 100% / 100% / 100% / 100%.
- **Tests:** `python3 -m unittest discover -s . -p 'test_*.py'` (53 tests).
- **Repo state:** `git status`

---

## Open questions / risks

- Real Groq call never exercised in this environment (no `GROQ_API_KEY`) —
  retry/fallback/validation are mock-tested; a live smoke test is the first
  thing to do where a key exists.
- Refund word-form parsing (`"five hundred dollars"`) is heuristic; the numeric
  paths (`$1,200`, `750 dollars`) are regex-tested.
- Prompt-injection is exercised via `eval_cases.csv` (5 injection rows, all
  escalate) and `test_adversarial.csv`.
- The decision log stores raw LLM output (email text minus keys); no API keys
  are ever logged — keep it that way.
