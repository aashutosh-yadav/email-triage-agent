from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

CATEGORIES = {"billing", "bug_report", "feature_request", "spam", "other"}
PRIORITIES = {"high", "medium", "low"}
ACTIONS = {"reply", "escalate_to_human", "ignore"}

REQUIRED_IN = ("id", "sender", "subject", "body")
REQUIRED_OUT = ("id", "category", "priority", "action", "reply_draft", "reason")

RE_SPAM = re.compile(r'\b(earn|click this link|viagra)\b', re.I)
RE_REFUND500 = re.compile(r'\brefund\s+over\s+\$\s*\d+\b', re.I)
RE_LEGAL = re.compile(r'\blegal\b', re.I)
RE_BREACH = re.compile(r'\b(data breach|security breach)\b', re.I)
RE_LEAK = re.compile(r'\b(data leak|leak)\b', re.I)
RE_THREAT = re.compile(r'\b(threat|lawsuit)\b', re.I)
RE_SSN = re.compile(r'\b(ssn)\b', re.I)
RE_PAYBLOCK = re.compile(r'\b(payment blocked|cannot pay)\b', re.I)
RE_OUTAGE = re.compile(r'\b(outage|unavailable|down|cannot log in)\b', re.I)
RE_BILLING = re.compile(r'\b(charge|invoice|billing|refund)\b', re.I)
RE_ADDR = re.compile(r'\b(address)\b', re.I)
RE_BUG = re.compile(r'\b(crash|error|broken|bug|not working|ne fonctionne pas|fonctionne pas)\b', re.I)
RE_FEAT = re.compile(r'\b(feature|integration|add)\b', re.I)
RE_THANKS = re.compile(r'\b(thanks|thank you)\b', re.I)

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
        if not reader.fieldnames or any(c not in reader.fieldnames for c in REQUIRED_IN):
            missing = [c for c in REQUIRED_IN if not reader.fieldnames or c not in reader.fieldnames]
            raise ValueError(f"missing required columns: {missing}")
        rows: List[Email] = []
        for i, row in enumerate(reader):
            rows.append(Email(id=(row.get("id") or "").strip(), sender=(row.get("sender") or "").strip(),
                              subject=(row.get("subject") or "").strip(), body=(row.get("body") or "").strip()[:10000]))
    return rows

def write_results(path: str | Path, results: Iterable[Triage]) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REQUIRED_OUT)); w.writeheader()
        for r in results:
            w.writerow({"id": r.id, "category": r.category, "priority": r.priority, "action": r.action, "reply_draft": r.reply_draft, "reason": r.reason})

def should_force_escalate(subject: str, body: str) -> Tuple[bool, str]:
    t = f"{subject} {body}"
    if RE_REFUND500.search(t): return True, "matches refund over $N"
    if RE_LEGAL.search(t): return True, "matches legal"
    if RE_BREACH.search(t): return True, "matches data/security breach"
    if RE_LEAK.search(t): return True, "matches data leak"
    if RE_THREAT.search(t): return True, "matches threat/lawsuit"
    if RE_SSN.search(t): return True, "matches ssn"
    if RE_PAYBLOCK.search(t): return True, "payment blocked/cannot pay"
    if RE_OUTAGE.search(t): return True, "outage/unavailable/down/cannot log in"
    return False, ""

def classify_email(email: Email) -> str:
    subj = email.subject
    body = email.body
    t = f"{subj} {body}"
    if RE_SPAM.search(t):
        return "spam"
    if RE_ADDR.search(t) and RE_BILLING.search(t):
        return "billing"
    if RE_BILLING.search(t):
        return "billing"
    if RE_BUG.search(t):
        return "bug_report"
    if RE_FEAT.search(t) and not RE_ADDR.search(t):
        return "feature_request"
    if RE_THANKS.search(t):
        return "other"
    if t.strip() == "":
        return "other"
    return "other"

def decide(email: Email, cat: str) -> Triage:
    subj = email.subject; body = email.body; t = f"{subj} {body}"
    forced, freason = should_force_escalate(subj, body)
    if cat == "spam":
        return Triage(id=email.id, category="spam", priority="low", action="ignore", reply_draft="", reason=f"spam: {freason or 'classified as spam'}; ignoring per policy.")
    if forced:
        return Triage(id=email.id, category=cat if cat in CATEGORIES else "other", priority="high", action="escalate_to_human", reply_draft="", reason=f"high priority: {freason}; escalating to human.")
    if cat == "bug_report":
        return Triage(id=email.id, category="bug_report", priority="high", action="escalate_to_human", reply_draft="", reason="functional bug likely blocking use; escalating to human.")
    if cat == "billing":
        return Triage(id=email.id, category="billing", priority="medium", action="reply", reply_draft="Thanks for flagging the issue. We'll review it and get back shortly. — The Support Team", reason="billing issue detected; actionable request -> reply.")
    if cat == "feature_request":
        return Triage(id=email.id, category="feature_request", priority="low", action="reply", reply_draft="Thanks for the suggestion. We've logged it for the product team. — The Support Team", reason="feature request; reply with acknowledgement.")
    if RE_THANKS.search(t):
        return Triage(id=email.id, category="other", priority="low", action="ignore", reply_draft="", reason="non-actionable thanks; ignoring.")
    if t.strip() == "":
        return Triage(id=email.id, category="other", priority="low", action="escalate_to_human", reply_draft="", reason="empty email content; escalating to human for review.")
    return Triage(id=email.id, category="other", priority="low", action="reply", reply_draft="Thanks for reaching out. We'll get back to you shortly. — The Support Team", reason="general inquiry; acknowledging.")

def validate_triage(t: Triage) -> None:
    if t.category not in CATEGORIES: raise ValueError(f"invalid category: {t.category}")
    if t.priority not in PRIORITIES: raise ValueError(f"invalid priority: {t.priority}")
    if t.action not in ACTIONS: raise ValueError(f"invalid action: {t.action}")
    rd = (t.reply_draft or "").strip()
    if t.action == "reply" and rd == "": raise ValueError("reply action requires non-empty reply_draft")
    if t.action != "reply" and rd != "": raise ValueError("non-reply action must have empty reply_draft")

def main() -> None:
    parser = argparse.ArgumentParser(prog="triage")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        emails = read_emails(args.input)
        out: List[Triage] = []
        for e in emails:
            try:
                forced, _ = should_force_escalate(e.subject, e.body)
                cat = classify_email(e)
                if cat == "spam" and forced:
                    cat = classify_email(e)  # keep spam but forced handled after
                t = decide(e, cat)
                validate_triage(t)
                out.append(t)
            except Exception:
                out.append(Triage(id=e.id, category="other", priority="high", action="escalate_to_human", reply_draft="", reason="failed to triage; escalating to human."))
        write_results(args.output, out)
        print(f"Wrote {len(out)} rows to {args.output}", file=sys.stderr)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
