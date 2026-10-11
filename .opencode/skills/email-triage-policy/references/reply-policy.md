# Reply Policy

Applies only when `action == reply`. Otherwise `reply_draft` is an empty string.

## Shape
- Friendly, professional, first person plural ("we").
- 60 words or fewer.
- Structure: acknowledge -> one concrete next step or question -> sign-off.
- No subject line; just the body.
- Reference nothing you cannot verify.

## Template

> Thanks for reaching out about {topic}. {Acknowledge the specific issue}.
> We're looking into it and will follow up shortly. If you can share
> {detail we need}, that will help us resolve it faster. — The Support Team

## Never include
- Promises of refunds, credits, discounts, or timelines you can't guarantee.
- Account data, tokens, internal IDs, or other customers' information.
- Legal or security assurances ("we guarantee no data was accessed").
- Confirmation that a bug is fixed before it is.

If the correct response would require any of the above, the action should be
`escalate_to_human`, not `reply`.

## Examples

Billing (medium) -> reply:
> Thanks for flagging the duplicate charge. We're reviewing the billing record
> now and will confirm the next step shortly. Could you share the invoice date
> shown in your statement? — The Support Team

Feature request -> reply:
> Thanks for the Slack integration idea — it's a sensible one. We've logged it
> for the product team and will reach out if we need more detail. — The Support Team
