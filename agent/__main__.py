from __future__ import annotations

import argparse
from pathlib import Path

from . import io
from . import rules


def main() -> None:
    p = argparse.ArgumentParser(prog="agent")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    emails = io.read_emails(args.input)
    results = []
    # End-to-end stub per terminal-triage-agent step 1
    for e in emails:
        subj = e.subject.lower()
        body = e.body.lower()
        if "spam" in subj or "earn" in body or "click this link" in body:
            cat = "spam"
            pri = "low"
            act = "ignore"
            rd = ""
            reason = "spam-like content detected; ignoring per policy."
        elif "charge" in body or "invoice" in subj or "billing" in body:
            cat = "billing"
            pri = "medium"
            act = "reply"
            rd = "Thanks for flagging the duplicate charge. We'll review it and get back shortly. — The Support Team"
            reason = "billing issue detected; actionable request -> reply."
        elif "crash" in body or "error" in body or "broken" in body:
            cat = "bug_report"
            pri = "high"
            act = "escalate_to_human"
            rd = ""
            reason = "functional bug likely blocking use; escalating to human."
        elif "feature" in subj or "integration" in subj or "add" in body:
            cat = "feature_request"
            pri = "low"
            act = "reply"
            rd = "Thanks for the suggestion. We've logged it for the product team. — The Support Team"
            reason = "feature request; reply with acknowledgement."
        elif "thanks" in body or "thank you" in subj:
            cat = "other"
            pri = "low"
            act = "ignore"
            rd = ""
            reason = "non-actionable thanks; ignoring."
        else:
            cat = "other"
            pri = "low"
            act = "reply"
            rd = "Thanks for reaching out. We'll get back to you shortly. — The Support Team"
            reason = "general inquiry; acknowledging."
        results.append(
            io.Triage(
                id=e.id,
                category=cat,
                priority=pri,
                action=act,
                reply_draft=rd,
                reason=reason,
            )
        )
    io.write_results(args.output, results)


if __name__ == "__main__":
    main()
