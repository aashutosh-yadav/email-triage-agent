# NOTES — progress & status (5-line updates per step)

## Step A — rule hardening (done, commit 785aa78)
- done: escalation-before-spam; spam needs >=2 signals ("earnings" removed); injection regex; outage ("app/site is down"); refund/dispute/legal/security/angry -> escalate; bug-with-workaround -> medium/reply. Rule asserts pass; runs clean on emails.csv + test_adversarial.csv.

## Step B — LLM wiring (done, commit 0cfffb9)
- done: GroqClient pydantic CategoryProposal (Literal), temperature 0, delimited <email> untrusted-data prompt, retry once w/ typed GroqError; agent.py falls back to regex on any LLM failure; --no-llm; decision log (out/decision_log.jsonl) records source llm|fallback per row; mock-verified retry+fallback.

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

## Step G — LLM trust, warnings, and small fixes (review #3)
- LLM spam cannot silently drop real mail: a model-proposed `spam` is accepted only when deterministic `is_spam()` agrees; otherwise fall back to the regex category and log `llm_note: llm_spam_rejected` (`classify_email` now returns a 5-tuple).
- Explicit LLM-unavailable warnings to stderr: import failure (captured in `LLM_IMPORT_ERROR`), init failure, or missing `GROQ_API_KEY`/`requests` via `GroqClient.is_configured()`; the final line states `llm` vs `regex-only`.
- Renamed typo `GrogError` -> `GroqError`; removed duplicate `Email` dataclass (agent.py owns it; agent_llm imports under `TYPE_CHECKING`).
- Groq default model `llama-3.1-8b-instant` was retired 2026-08-16 -> default now `openai/gpt-oss-20b` (.env.example updated).
- `python -m agent` -> `python3 agent.py` in PROJECT_CONTEXT.md and the build skill; `opencode.jsonc` no longer hardcodes a machine-specific path (`skills: [".opencode/skills"]`).

## Step H — rule generalization + held-out eval sets (review #3)
- Fixed generalization gaps: data loss ("reports disappeared", "lost months of work") -> bug_report/high/escalate; feature-request phrasings ("would be lovely if you could add", "any chance you could add", "would it be possible to add") -> feature_request; French crash/blocking ("plante", "impossible de l'utiliser").
- Planned-maintenance guard: "down for maintenance" is not an unplanned outage.
- Added 14 tests (rules 39, LLM 14 = 53 total; all pass).
- Held-out sets (authored from policy, not tuned): `heldout_cases.csv` 26 rows -> category 73.1 / priority 96.2 / action 88.5 (pre-fix); `heldout_cases_2.csv` 20 rows -> 80.0 / 85.0 / 85.0 (post data-loss+feature fixes); `heldout_cases_3.csv` 16 rows (current code) -> 100 / 100 / 100. Documented remaining limitations (single-signal spam, non-English beyond French, generic "fails", cosmetic/ambiguous labels).
- Note: #1 and #2 are now "seen" (their genuine failures drove the fixes); #3 is the fresh post-fix measure.

## Final state
- Commits: A(785aa78), B(0cfffb9), C(edd89a1), D(023f123), E(4c45360), F(32a271d).
- Working tree: agent single entry point `agent.py`; LLM via Groq (pydantic, retry-once, temp 0, delimited, default `openai/gpt-oss-20b`); model spam distrusted unless regex agrees; clear warnings when LLM unavailable; deterministic `--no-llm` path; decision log `out/decision_log.jsonl` (no secrets).
- Eval/tests: 53/53 unittest tests OK; `python3 eval.py` -> category=priority=action=100%, escalation-action=100%, no mismatches, no reply_draft violations. Held-out #3 100% (16/16).
- Risks: live Groq key not tested here (mocked only); non-English + single-signal spam coverage is partial (documented in README).