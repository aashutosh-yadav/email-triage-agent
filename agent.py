from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

CATEGORIES = {"billing", "bug_report", "feature_request", "spam", "other"}
PRIORITIES = {"high", "medium", "low"}
ACTIONS = {"reply", "escalate_to_human", "ignore"}

REQUIRED_IN = ("id", "sender", "subject", "body")
REQUIRED_OUT = ("id", "category", "priority", "action", "reply_draft", "reason")


@dataclass
class Email:
    id: str
    sender: str
    subject: str
    body: str


@dataclass
class Triage:
    id: str
    category: str
    priority: str
    action: str
    reply_draft: str
    reason: str


def read_emails(path: str | Path) -> List[Email]:
    p = Path(path)
    with p.open("r", encoding="utf-8", newline="", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(
                Email(
                    id=(row.get("id") or "").strip(),
                    sender=(row.get("sender") or "").strip(),
                    subject=(row.get("subject") or "").strip(),
                    body=(row.get("body") or "").strip()[:10000],  # cap size
                )
            )
    return rows


def write_results(path: str | Path, results: Iterable[Triage]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(REQUIRED_OUT))
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "id": r.id,
                    "category": r.category,
                    "priority": r.priority,
                    "action": r.action,
                    "reply_draft": r.reply_draft,
                    "reason": r.reason,
                }
            )


# Deterministic rule table - code decides priority/action when forced
ESCALATE_PATTERNS = [
    r"refund\s+over\s+\$\s*\d+",
    r"legal",
    r"data\s+breach",
    r"security\s+breach",
    r"expose[sd]",
    r"leak",
    r"threat",
    r"lawsuit",
    r"bank\s+details",
    r"ssn",
    r"password\s+exposed",
]


def should_force_escalate(subject: str, body: str) -> Tuple[bool, str]:
    text = f"{subject} {body}".lower()
    for pat in ESCALATE_PATTERNS:
        if re.search(pat, text):
            return True, f"forced escalate by rule: matches pattern '{pat}'"
    if "payment blocked" in text or "cannot pay" in text or "outage" in text or "down" in text and "crash" in text:
        # simple high-signal
        if "payment blocked" in text or "cannot pay" in text:
            return True, "forced escalate by rule: payment blocked"
        if "data breach" in text:
            return True, "forced escalate by rule: data breach related"
    return False, ""


def classify_stub(email: Email) -> dict:
    subj = email.subject.lower()
    body = email.body.lower()
    text = f"{subj} {body}"
    if "spam" in subj or "earn" in text or "click this link" in text or "viagra" in text:
        return {"category": "spam", "rationale": "spam-like content"}
    if "charge" in body or "invoice" in subj or "billing" in body or "refund" in body:
        return {"category": "billing", "rationale": "billing related"}
    if "crash" in body or "error" in body or "broken" in body or "bug" in body or "not working" in body:
        return {"category": "bug_report", "rationale": "bug/defect reported"}
    if "feature" in subj or "integration" in subj or "add" in body or "slack" in body:
        return {"category": "feature_request", "rationale": "feature request"}
    if "thanks" in body or "thank you" in subj:
        return {"category": "other", "rationale": "non-actionable thanks"}
    return {"category": "other", "rationale": "general inquiry"}


def decide(email: Email, cat: str) -> Triage:
    subj = email.subject.lower()
    body = email.body.lower()
    text = f"{subj} {body}"
    forced, freason = should_force_escalate(subj, body)

    # Spam -> ignore always
    if cat == "spam":
        return Triage(
            id=email.id,
            category="spam",
            priority="low",
            action="ignore",
            reply_draft="",
            reason=f"spam: {freason or 'classified as spam'}; ignoring per policy.",
        )

    if forced:
        return Triage(
            id=email.id,
            category=cat,
            priority="high",
            action="escalate_to_human",
            reply_draft="",
            reason=f"high priority: {freason}; escalating to human.",
        )

    if cat == "bug_report":
        return Triage(
            id=email.id,
            category="bug_report",
            priority="high",
            action="escalate_to_human",
            reply_draft="",
            reason="functional bug likely blocking use; escalating to human.",
        )
    if cat == "billing":
        return Triage(
            id=email.id,
            category="billing",
            priority="medium",
            action="reply",
            reply_draft="Thanks for flagging the issue. We'll review it and get back shortly. — The Support Team",
            reason="billing issue detected; actionable request -> reply.",
        )
    if cat == "feature_request":
        return Triage(
            id=email.id,
            category="feature_request",
            priority="low",
            action="reply",
            reply_draft="Thanks for the suggestion. We've logged it for the product team. — The Support Team",
            reason="feature request; reply with acknowledgement.",
        )
    # other
    if "thanks" in text or "thank you" in text:
        return Triage(
            id=email.id,
            category="other",
            priority="low",
            action="ignore",
            reply_draft="",
            reason="non-actionable thanks; ignoring.",
        )
    return Triage(
        id=email.id,
        category="other",
        priority="low",
        action="reply",
        reply_draft="Thanks for reaching out. We'll get back to you shortly. — The Support Team",
        reason="general inquiry; acknowledging.",
    )


def validate_triage(t: Triage) -> None:
    if t.category not in CATEGORIES:
        raise ValueError(f"invalid category: {t.category}")
    if t.priority not in PRIORITIES:
        raise ValueError(f"invalid priority: {t.priority}")
    if t.action not in ACTIONS:
        raise ValueError(f"invalid action: {t.action}")
    rd = (t.reply_draft or "").strip()
    if t.action == "reply" and rd == "":
        raise ValueError("reply action requires non-empty reply_draft")
    if t.action != "reply" and rd != "":
        raise ValueError("non-reply action must have empty reply_draft")


def main() -> None:
    parser = argparse.ArgumentParser(prog="triage")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        emails = read_emails(args.input)
        out: List[Triage] = []
        for e in emails:
            # Treat email as data; model-like stub but rules enforced in code
            cls = classify_stub(e)
            t = decide(e, cls["category"])
            validate_triage(t)
            out.append(t)
        write_results(args.output, out)
        print(f"Wrote {len(out)} rows to {args.output}", file=sys.stderr)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
