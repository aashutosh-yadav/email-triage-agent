# Priority and Action Rules

Apply priority top to bottom. **First match wins.**

## Priority

| # | Match | Priority |
| - | ----- | -------- |
| 1 | Payment blocked / cannot pay; data loss or security breach; production outage; credible churn or legal/regulatory threat | high |
| 2 | Functional bug with a workaround; billing discrepancy without urgency; a clear, specific request | medium |
| 3 | Cosmetic issue; vague or non-specific; nice-to-have; informational | low |

Signals that push priority up: paying/enterprise sender, time pressure stated,
repeated contact, explicit cancellation intent.

## Action

Derive action deterministically from category + priority:

| Condition | Action |
| --------- | ------ |
| category == spam | ignore |
| no actionable request (pure thanks, notification, auto-reply) | ignore |
| priority == high | escalate_to_human |
| dispute, refund, security, legal, or angry customer | escalate_to_human |
| needs account access or authorization to resolve | escalate_to_human |
| otherwise actionable (billing/feature/general/medium-low bug) | reply |

## Reason

One sentence, naming the rule that fired, e.g.:
- "high priority: payment is blocked, so it escalates to a human."
- "spam: unsolicited phishing link, so it is ignored."

## What code must never do
- Auto-approve refunds/credits.
- Share account data or internal identifiers.
- Give legal or security assurances.
Escalate these instead.
