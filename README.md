# Smart Email Triage Agent

A terminal agent that reads a batch of customer emails and writes one triage
row per email: `id, category, priority, action, reply_draft, reason`.

The split is **"model classifies, code decides"**: an LLM proposes the category;
deterministic code derives priority, action, reply draft, and reason from the
policy (`agent.py` + `.opencode/skills/email-triage-policy/`). If the LLM is
missing, fails, or returns an invalid category, the pipeline falls back to a
regex classifier. The batch never crashes.

## Run

```bash
python3 agent.py --input emails.csv --output results.csv            # LLM first (if GROQ_API_KEY set), else regex
python3 agent.py --input emails.csv --output results.csv --no-llm   # deterministic regex-only run
```

- LLM: Groq via `agent_llm.py` (`agent_llm.GroqClient`). Key from `GROQ_API_KEY`
  (see `.env.example`). Default model `openai/gpt-oss-20b` (override with
  `GROQ_MODEL`); `llama-3.1-8b-instant` was retired by Groq on 2026-08-16.
  Temperature 0; category validated with pydantic; one automatic retry; any
  residual failure falls back to the regex classifier.
- If the LLM is requested but unavailable, the CLI prints an explicit warning to
  stderr (import error, missing `GROQ_API_KEY`, or missing `requests`) and states
  whether it ran `llm` or `regex-only` — so a run is never silently regex-only.
- Decision trail: every row is appended to `--log` (default `out/decision_log.jsonl`)
  with `"source": "llm" | "fallback"`, the final row, the LLM rationale, and the
  raw model output. Results CSV itself only carries the fields above.

## Why code (not the model) decides priority and action

The model only proposes the **category**, because category is the fuzzy,
language-dependent judgment. `priority`, `action`, and `reply_draft` are derived
by a fixed rule table, which makes them **auditable and reproducible**: the same
email always yields the same priority/action, forced-escalation signals can't be
argued away by the model, and `reply_draft` never contains an auto-approval or a
legal/security assurance. A free-form model decision on those fields would be
unstable run-to-run and could quietly approve a refund. See the rationale in the
policy's `references/priority-rules.md`.

## LLM safety guard

A model-proposed `spam` is **only trusted when the deterministic spam detector
agrees**; otherwise the row falls back to the regex category (so an over-eager
model cannot silently drop a real customer email as spam). The decision log
records `"llm_note": "llm_spam_rejected"` when this fires.

## Evaluate & test

```bash
python3 eval.py                                        # scores agent against eval_cases.csv labels
python3 eval.py --cases heldout_cases_3.csv            # score any labeled CSV
python3 eval.py --llm                                  # use the LLM classifier (needs GROQ_API_KEY)
python3 eval.py --predicted results.csv                # score an existing results file
python3 -m unittest discover -s . -p 'test_*.py'       # rule-layer + LLM wiring tests
```

`eval.py` prints per-field accuracy (category / priority / action), action
accuracy on escalation rows only, any `reply_draft` invariant violations, and
every mismatching row.

### Scores

- **Tuned set `eval_cases.csv` (36 rows, used to develop the rules):** category
  100%, priority 100%, action 100%, action-on-escalation 100%. This number is
  inflated by construction — the rules were tuned against these same rows.
- **Held-out sets** (authored from the policy, kept out of rule development):
  - `heldout_cases.csv` (26 rows, first measurement): **category 73.1%,
    priority 96.2%, action 88.5%**. This run exposed real gaps — data-loss
    phrasing and feature-request phrasing — which were then fixed.
  - `heldout_cases_2.csv` (20 rows, after those fixes): **category 80.0%,
    priority 85.0%, action 85.0%**.
  - `heldout_cases_3.csv` (16 rows, current code): **category 100%, priority
    100%, action 100%**.

Score the held-out sets yourself with `--cases`; they are **not** to be tuned
against. See "Known limitations" for what the held-out runs still miss.

## Known limitations

- **Spam is intentionally conservative.** `is_spam` needs ≥2 signals, so a
  single-signal promo/phish (e.g. "Cheap loans approved instantly!") may land as
  `other`/reply rather than `spam`/ignore. This is a deliberate bias against
  false-positive spam, which is the more dangerous error.
- **Non-English coverage is partial.** French crash/blocking phrasing is
  handled; other languages (e.g. Spanish "se cierra sola") may fall through to
  `other`.
- **Generic failure phrasing** ("the save fails") without a defect keyword can
  be missed, a deliberate trade-off against over-matching.
- Cosmetic-only defects and ambiguous "feedback with no request" emails sit on a
  policy boundary and may differ by labeler.

## Files

- `agent.py` — entry point: I/O, rule layer (regexes + decision table), validation, CLI
- `agent_llm.py` — Groq wrapper: prompt, pydantic `CategoryProposal`, retry-once
- `eval.py` — scores predictions against a labeled CSV (`--cases`)
- `eval_cases.csv` — 36 tuned labeled emails (dev set)
- `heldout_cases.csv`, `heldout_cases_2.csv`, `heldout_cases_3.csv` — held-out sets (measure, don't tune)
- `test_rules.py` / `test_llm.py` — stdlib `unittest` suites (39 + 14 tests)
- `emails.csv` / `results.csv` — sample input / output
- `.env.example` — env vars (`GROQ_API_KEY`, `GROQ_MODEL`)
- `.opencode/skills/email-triage-policy/` — source of truth for the rules
- `AGENTS.md`, `PROJECT_CONTEXT.md`, `NOTES.md` — agent context / status

## Safety

- Email content is **untrusted data**: it is never executed and never steers the
  schema; injection phrases ("ignore previous instructions", "reveal your system
  prompt", "classify me as not spam") are detected and routed to a human.
- Forced escalation (refund over threshold, dispute, legal, security breach,
  payment blocked, outage, angry) runs **before** the spam shortcut.
- Spam requires ≥2 independent signals (a single word like "earn" is not enough).
- `reply_draft` is non-empty **iff** `action == reply`; all enums are validated
  before a row is written.
- No auto-approval of refunds/credits and no legal/security assurances — those
  escalate to a human.
