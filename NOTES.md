# NOTES — progress & status (5-line updates per step)

## Step A — rule hardening (regex, no LLM yet)
- done: rewrote agent.py rule layer — escalation rules run before the spam shortcut; spam now needs >=2 signals ("earnings" removed); added prompt-injection, outage ("app/site is down"), dispute/refund/legal/security escalation; bug-with-workaround -> medium/reply; blocking bugs -> high/escalate.
- verified: `python agent.py --input emails.csv --output results.csv` runs clean; enums + reply_draft invariant hold.
- next: Step B LLM wiring (agent_llm.py + --no-llm + decision log).
- known issues: none yet; eval_cases.csv not built yet.