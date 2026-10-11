# NOTES — progress & status (5-line updates per step)

## Step A — rule hardening (done, commit 785aa78)
- done: escalation rules run BEFORE the spam shortcut; spam needs >=2 distinct signals ("earnings" removed); prompt-injection regex covers "ignore your instructions"/"previous rules"; outage ("app/site is down") escalates; refund/dispute/legal/security/angry -> escalate; bug-with-workaround -> medium/reply, blocking bug -> high/escalate. Rule-layer asserts pass; emails.csv + test_adversarial.csv run clean.
- verified: `python agent.py --input emails.csv --output results.csv` OK on both fixtures; enum/reply_draft invariants hold.
- next: Step B — wire agent_llm.py (pydantic validation, retry once, temp 0, delimited prompt), add --no-llm + decision log.
- known issues: none confirmed; real LLM untestable here (no GROQ_API_KEY) -> mock in tests.