# Smart Email Triage Agent

Terminal agent that reads a batch of emails and classifies each one (category, priority, action, reply draft, reason).

## How it works

We split responsibility: **model suggests**; **code enforces rules**.

- `agent.py` reads `emails.csv` and writes `results.csv` (single-file entry point, matches requested invocation `python agent.py ...`).
- Email content is treated as **untrusted data** (prompt-injection guard). The agent does not follow instructions embedded in emails; it extracts signals only.
- **Forced escalation** rules run in deterministic code (refund amounts, "legal", "data breach", "payment blocked", etc.) and override any classification. Spam is always `ignore` with no reply.
- `reply_draft` is non-empty iff `action == reply`. All enums validated before writing.

## Run

```bash
python agent.py --input emails.csv --output results.csv
```

## Files

- `agent.py` — I/O, validation, rule enforcement, deterministic classifier
- `agent/` — package (io, rules, model placeholder, CLI) — kept for structure
- `emails.csv` — sample input
- `results.csv` — sample output on emails.csv
- `test_adversarial.csv` / `test_adversarial_results.csv` — adversarial tests
- `eval.py` — simple per-field accuracy checker
- `AGENTS.md`, `PROJECT_CONTEXT.md`, `.opencode/skills/` — design/skills (source of truth for rules)
- `requirements.txt` — deps

## Design notes

- Code decides priority/action where safety matters (escalations, spam). Model is not trusted to unilaterally change these.
- Size limits (email body capped), defensive CSV reading, clear validation errors.
- Avoids an agent loop (fixed pipeline) for determinism and speed.

## Self-answers

- **Model vs code**: model would propose category/rationale in a real LLM version; code enforces forced escalations, action/priority invariants, and `reply_draft` constraints (never let email text override schema/rules).
- **Invalid JSON**: validate schema/enums, repair or fall back to safe defaults; never crash a whole batch for one row (fail fast with clear error here).
- **Manipulation**: treat subject/body as data only, pattern-based escalation in code, ignore instruction strings, and never execute email content.
- **Next 24h**: plug real LLM with JSON mode + retry/timeout, add more adversarial cases, proper eval with ground truth, batch logging, and better repair logic.
