# Taxonomy

Assign **exactly one** category. When two seem plausible, choose the one that
best matches the customer's *intent*, not surface words.

## billing
Money, payments, and plans.
- Invoices, receipts, charges, refunds, credits
- Payment method changes, failed payments
- Subscription upgrades/downgrades/cancellation
- Pricing and plan questions

Example: "I was charged twice this month." -> billing

## bug_report
Something that used to work (or should work) is broken.
- Errors, exceptions, crashes, 500s
- Data loss or corruption
- Regressions after an update
- "Not working" reports with a defect

Example: "Export button does nothing since yesterday." -> bug_report

## feature_request
A request for a capability that does not exist yet.
- New features, enhancements, integrations
- Workflow changes the customer wants built

Example: "Can you add a Slack integration?" -> feature_request

## spam
Unsolicited or malicious mail with no genuine customer intent.
- Marketing/promotional blasts, SEO/link offers
- Phishing, scam, spoofed senders, credential harvesting
- Bulk irrelevant mail

Example: "Your account is suspended, click here to verify." -> spam

## other
Genuine mail that fits none of the above.
- General questions, "how do I..." that is not a defect
- Praise, feedback, partnership, press, hiring, legal notices

Example: "Thanks, the new dashboard is great." -> other

## Boundary cases
- Bug report that blocks payment -> category `bug_report`,
  but priority `high` and action `escalate_to_human` (see priority rules).
- Angry email with no clear request -> `other`, likely `escalate_to_human`.
- Feature request from a paying customer -> `feature_request`, often `reply`.
