# NOTES — progress & status (5-line updates per step)

## Step A — rule hardening (done, commit 785aa78)
- done: escalation-before-spam; spam needs >=2 signals ("earnings" removed); injection regex; outage ("app/site is down"); refund/dispute/legal/security/angry -> escalate; bug-with-workaround -> medium/reply. Rule asserts pass; runs clean on emails.csv + test_adversarial.csv.

## Step B — LLM wiring (done, commit 0cfffb9)
- done: GroqClient pydantic CategoryProposal (Literal), temperature 0, delimited <email> untrusted-data prompt, retry once w/ typed GrogError; agent.py falls back to regex on any LLM failure; --no-llm; decision log (out/decision_log.jsonl) records source llm|fallback per row; mock-verified retry+fallback.

## Step C — single entry point (done, commit edd89a1)
- done: deleted stale agent/ package; `import agent` resolves to agent.py; runs clean.

## Step E — cleanup (done, commit 4c45360)
- Trimmed requirements.txt (removed httpx).
- Created .env.example, added `!.env.example` exception in .gitignore, added `*.zip` to ignore.
- Rewrote README.md; refreshed PROJECT_CONTEXT.md (status, repo map, decisions, verification).
- `git commit -m "Clean up: trim deps, add .env.example, ignore *.zip, refresh README + project context"` (4c45360).

## Step F — apply reviewer findings (done, commit 32a271d)
- Refund scoping: nearest amount to each "refund" (so $10 refund on $600 invoice no longer escalates). Over-flag honors >= threshold.
- Injection: tightened regex to require a hardsign (previous/your/above/system/developer); drops benign "earlier instructions" cases while preserving canonical attacks.
- RE_BUG: scoped to product/defect contexts; added `does nothing`, `perf...slowed`, `slowed down`, product-specific lag; removed overly broad `fail\w*`, `problem with`/`issue with` (unqualified).
- RE_BILLING: `plan\b` replaced with money/subscription context (pro/basic/etc plan, plan price/cost/changes, upgrade/downgrade/cancel/change plan).
- Non-actionable: added Out-of-office/automated markers; check non-actionable BEFORE question in decide (thanks+question can still reply if question detected).
- eval.py: UTF-8 with errors="replace", robust `load_predicted` (header/id checks, duplicate detection), removed synthetic duplicate mismatch entry.
- main: write decision log BEFORE results.csv.
- Added targeted regression tests in test_rules.py. Regenerated `results.csv`. All 36 tests pass; eval 100%/100%/100% escalation 100%, 0 reply_draft violations.

## Final state
- Commits: A(785aa78), B(0cfffb9), C(edd89a1), D(023f123), E(4c45360), F(32a271d).
- Working tree clean. Agent single entry point `agent.py`. LLM via Groq (pydantic, retry-once, temp 0, delimited). Deterministic `--no-llm` path. Decision log `out/decision_log.jsonl` (no secrets). Policy references updated (forced-escalation-before-spam carve-out; refund $500 threshold with explanation).
- Eval/tests: 36/36 unittest tests OK; `python3 eval.py` → category=priority=action=100%, escalation-action=100%, no mismatches, no reply_draft violations.
- Risks: live Groq key not tested here (mocked); refund word-form parsing is heuristic.