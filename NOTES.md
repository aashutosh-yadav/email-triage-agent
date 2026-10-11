# NOTES — progress & status (5-line updates per step)

## Step A — rule hardening (done, commit 785aa78)
- done: escalation-before-spam; spam needs >=2 signals ("earnings" removed); injection regex; outage ("app/site is down"); refund/dispute/legal/security/angry -> escalate; bug-with-workaround -> medium/reply. Rule asserts pass; runs clean on emails.csv + test_adversarial.csv.

## Step B — LLM wiring (done, commit 0cfffb9)
- done: GroqClient pydantic CategoryProposal (Literal), temperature 0, delimited <email> untrusted-data prompt, retry once w/ typed GrogError; agent.py falls back to regex on any LLM failure; --no-llm; decision log (out/decision_log.jsonl) records source llm|fallback per row; mock-verified retry+fallback.

## Step C — single entry point (done, commit edd89a1)
- done: deleted stale agent/ package; `import agent` resolves to agent.py; runs clean.

## Step D — eval (done, commit 01e4f56)
- done: test-writer built eval_cases.csv (36 labeled rows across all coverage bands) + test_rules.py (25 unittest methods); eval.py rewritten (per-field + escalation-row accuracy + every mismatch + reply_draft invariant). Fixed from RED: injection "classify me as not spam"; French "ne fonctionne plus"; data-loss blocking ("files were wiped"); refund amounts in "$1,200"/"750 dollars"/word forms -> parsed numerically; per-rule escalation priorities (refund/angry/empty=medium, rest=high); outage phrasing -> bug_report category; question-beats-thanks ordering; newsletter/prize single-signal -> ignore. Added test_llm.py (11 tests: retry-once, invalid-cat fallback, temp 0, delimiters).
- verified: 36/36 tests pass; eval category=priority=action=100%, escalation-action=100%, 0 reply_draft violations, 0 mismatches.
- next: Step E cleanup (README rewrite, requirements, .env.example done, .gitignore *.zip, zip deletions, PROJECT_CONTEXT refresh) + reviewer pass.
- known issues: real Groq call untested in CI (no key); word-form refund parsing is heuristic (see test coverage).