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
python agent.py --input emails.csv --output results.csv   # LLM first (if GROQ_API_KEY set), else regex
python agent.py --input emails.csv --output results.csv --no-llm   # deterministic regex-only run
```

- LLM: Groq via `agent_llm.py` (`agent_llm.GroqClient`). Key from `GROQ_API_KEY`
  (see `.env.example`). Temperature 0; category validated with pydantic; one
  automatic retry; any residual failure falls back to the regex classifier.
- Decision trail: every row is appended to `--log` (default `out/decision_log.jsonl`)
  with `"source": "llm" | "fallback"`, the final row, the LLM rationale, and the
  raw model output. Results CSV itself only carries the fields above.

## Evaluate & test

```bash
python eval.py                                       # scores agent against eval_cases.csv labels
python eval.py --predicted results.csv               # score an existing results file
python -m unittest discover -s . -p 'test_*.py'      # rule-layer + LLM wiring tests
```

`eval.py` prints per-field accuracy (category / priority / action), action
accuracy on escalation rows only, any `reply_draft` invariant violations, and
every mismatching row. Current numbers on `eval_cases.csv` (36 rows):
**category 100%, priority 100%, action 100%, action-on-escalation 100%.**

## Files

- `agent.py` — entry point: I/O, rule layer (regexes + decision table), validation, CLI
- `agent_llm.py` — Groq wrapper: prompt, pydantic `CategoryProposal`, retry-once
- `eval.py` — scores predictions against `eval_cases.csv` labels
- `eval_cases.csv` — 36 labeled emails: normal, injection, non-English, empty, long, ambiguous, spam-bait
- `test_rules.py` / `test_llm.py` — stdlib `unittest` suites (25 + 11 tests)
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