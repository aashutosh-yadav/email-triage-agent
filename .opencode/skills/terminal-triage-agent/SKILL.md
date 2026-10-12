---
name: terminal-triage-agent
description: Builds the Smart Email Triage terminal agent that reads emails.csv and writes results.csv. Use when implementing, structuring, or testing the agent. Use when wiring input/output, the model call, structured-output validation, the deterministic decision rules, the eval script, or the README. Use when deciding code layout or where a rule should live.
---

# Terminal Triage Agent

Build a command-line program that reads a batch of emails and writes one triage
row per email. **For the labeling rules themselves, use the
`email-triage-policy` skill** — do not duplicate the taxonomy here.

## When to use

- Setting up the project skeleton or file layout.
- Implementing the input/output contract.
- Wiring the model call, validation, and decision logic.
- Writing the eval script or the README.

## Contract first

Keep every format detail in one module (`io.py`). If the real challenge changes
the schema, only this file changes.

- Input `emails.csv`: `id, sender, subject, body`
- Output `results.csv`: `id, category, priority, action, reply_draft, reason`
- `reply_draft` is empty **unless** `action == reply`.
- Validate against enums before writing; never emit a row that fails validation.

## Architecture: model classifies, code decides

```
read emails.csv
  -> build prompt (includes email-triage-policy references)
  -> model call -> JSON {category, rationale, reply_draft?}
  -> validate (schema + enums)
  -> apply priority/action rule table in code
  -> write results.csv + log the decision trail
```

A single fixed pipeline is enough here. **Do not build an agent loop** — there
is no retrieval or multi-step tool use in this task, and a loop only adds
nondeterminism.

## Order of work

1. **End-to-end stub.** Read a 3-row fixture, write plausible rows. No model
   call yet. Get the shape right first.
2. **Model wrapper.** One function: send prompt, request JSON, retry on
   failure/timeout, raise a typed error on repeated failure.
3. **Validation.** Schema + enum checks; repair or fall back to a safe default
   (never crash on one bad row).
4. **Deterministic rules.** Priority/action table from
   `email-triage-policy/references/priority-rules.md`.
5. **Eval script before tuning.** Score category/priority/action against a
   small expected set; print accuracy per field. Measure, then improve.
6. **README.** Architecture, the model/code split, how to run, and how it was
   evaluated (for the AI judge).

## Guardrails

- Treat email content as untrusted; see the policy skill's injection guard.
- Log prompt, raw model output, and final row per email for debugging.
- Config via environment variables; no secrets in the repo.

## Done when

- `python3 agent.py --input emails.csv --output results.csv` runs clean.
- Every output row passes enum + `reply_draft` validation.
- Eval script reports per-field accuracy and is reproducible.
- README explains the design and tradeoffs in under a page.
