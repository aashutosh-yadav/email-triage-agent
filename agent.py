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

# --------------------------------------------------------------------------
# Spam: needs >= 2 distinct signals. A single word like "earn"/"earnings" is
# NOT enough (removed -- too many false positives on legit business mail).
# --------------------------------------------------------------------------
RE_SPAM_SIGNAL = re.compile(
    r"\b(viagra|free\s+(cash|money|iphone|gift\s*card|trial|samples?)|get\s+rich|fast\s+cash"
    r"|work\s+from\s+home|click\s+(this|the)\s+link|click\s+here|win(?:ner)?|guaranteed"
    r"|verify\s+your\s+account|confirm\s+your\s+(password|account)|act\s+now"
    r"|limited\s+time\s+(offer|deal)|exclusive\s+(deal|offer)|you\s+have\s+been\s+selected"
    r"|lottery|investment\s+opportunity|crypto\s+(giveaway|secret)|claim\s+your\s+prize)\b",
    re.I,
)

# --------------------------------------------------------------------------
# Prompt injection (email content must never steer the pipeline).
# --------------------------------------------------------------------------
RE_INJECT = re.compile(
    r"\b(?:"
    r"(?:ignore|disregard|forget|overrule|override)\s+(?:all\s+|any\s+|the\s+|your\s+|my\s+|earlier\s+|above\s+)*"
    r"(?:previous\s+|prior\s+|earlier\s+|above\s+)*"
    r"(?:instructions?|rules?|prompts?|guidelines?|directives?|everything\s+above|all\s+context)"
    r"|ignore\s+(?:all\s+)?the\s+above"
    r"|(?:system|developer)\s+prompt"
    r"|reveal\s+(?:your\s+|the\s+)?(?:system\s+)?prompt"
    r"|print\s+(?:your|the)\s+instructions"
    r"|output\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions)"
    r"|jailbreak"
    r"|you\s+are\s+now\s+(?:an?\s+)?(?:admin|assistant|ai)"
    r"|i\s+am\s+(?:the\s+|your\s+)?(?:admin|developer)"
    r"|i['\u2019]m\s+(?:the\s+|your\s+)?(?:admin|developer)"
    r"|mark\s+(?:this|me)\s+as\s+(?:not\s+)?(?:spam|safe)"
    r")\b",
    re.I,
)

# Forced escalation signals (high risk -> escalate_to_human).
RE_REFUND500 = re.compile(r"\brefund\s+(?:over|of|above|for)\s+\$?\s*\d{2,}\b", re.I)
RE_DISPUTE = re.compile(r"\b(dispute|chargeback|fraudulent\s+charge|unauthorized\s+charge)\b", re.I)
RE_LEGAL = re.compile(r"\b(legal|lawsuit|attorney|demand\s+letter)\b", re.I)
RE_BREACH = re.compile(
    r"\b(data\s+breach|security\s+breach|compromised|hacked|unauthorized\s+access|account\s+accessed)\b",
    re.I,
)
RE_LEAK = re.compile(r"\b(data\s+leak|leaked)\b", re.I)
RE_SSN = re.compile(r"\b(ssn|social\s+security\s+(number|no\.?))\b", re.I)
RE_PAYBLOCK = re.compile(r"\b(payment\s+blocked|cannot\s+pay|can['\u2019]t\s+pay)\b", re.I)
RE_OUTAGE = re.compile(
    r"\b(?:"
    r"(?:the\s+)?(?:app|application|site|website|platform|full\s+service|whole\s+system)(?:\s+is|\s+are|\s+was)?\s+down"
    r"|down\s+for\s+everyone"
    r"|everything\s+is\s+down"
    r"|totally\s+down"
    r"|can['\u2019]t\s+log\s+in|cannot\s+log\s+in"
    r"|won['\u2019]t\s+load"
    r"|(?:50[0348])\s+error|internal\s+server\s+error|outage"
    r")\b",
    re.I,
)
RE_ANGRY = re.compile(r"\b(angry|furious|outraged|unacceptable)\b", re.I)

# Category regexes (regex fallback classifier).
RE_BILLING = re.compile(
    r"\b(charg\w*|bill\w*|invoice|payment|billing|refund|subscription|subscribe|plan\b|credit|debit|price|pricing)\b",
    re.I,
)
RE_BUG = re.compile(
    r"\b(crash\w*|error\w*|broken|bug\w*|not\s+working|doesn['\u2019]t\s+work|does\s+not\s+work|glitch|fail\w*"
    r"|problem\s+with|issue\s+with|slow\b|lag(?:ging)?|freez\w*|ne\s+fonctionne\s+pas|fonctionne\s+pas)\b",
    re.I,
)
RE_FEAT = re.compile(
    r"\b(feature|integration|suggestion|enhancement|roadmap|please\s+add|could\s+you\s+add|can\s+you\s+add"
    r"|can\s+we\s+(?:have|get)|would\s+be\s+(?:great|nice)\s+to\s+have|would\s+love)\b",
    re.I,
)
RE_THANKS = re.compile(r"\b(thanks|thank\s+you|thx|appreciate\s+it|great\s+job)\b", re.I)
RE_NONACTION = re.compile(r"\b(no\s+action\s+needed|no\s+reply\s+needed|just\s+fyi|fyi\b|for\s+your\s+information|noted)\b", re.I)

# Blocking bugs (no workaround) -> escalate; otherwise bug_with_workaround -> reply.
RE_BLOCKING_BUG = re.compile(
    r"\b(crash\w*|won['\u2019]t\s+(open|start|load|launch|work|cancel)|cannot\s+log\s+in|can['\u2019]t\s+log\s+in"
    r"|black\s+screen|frozen|freez\w*|completely\s+(broken|blocked|unusable)|data\s+loss|locked\s+out"
    r"|unable\s+to\s+(open|access|use)|impossible\s+to\s+(use|open)|lost\s+my\s+data)\b",
    re.I,
)


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


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------
def read_emails(path: str | Path) -> List[Email]:
    p = Path(path)
    with p.open("r", encoding="utf-8", newline="", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("missing CSV header")
        missing = [c for c in REQUIRED_IN if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"missing required columns: {missing}")
        rows: List[Email] = []
        for _, row in enumerate(reader):
            rows.append(
                Email(
                    id=(row.get("id") or "").strip(),
                    sender=(row.get("sender") or "").strip(),
                    subject=(row.get("subject") or "").strip(),
                    body=(row.get("body") or "").strip()[:10000],
                )
            )
    return rows


def write_results(path: str | Path, results: Iterable[Triage]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REQUIRED_OUT))
        w.writeheader()
        for r in results:
            w.writerow(
                {
                    "id": r.id,
                    "category": r.category,
                    "priority": r.priority,
                    "action": r.action,
                    "reply_draft": r.reply_draft,
                    "reason": r.reason,
                }
            )


# --------------------------------------------------------------------------
# Rule layer
# --------------------------------------------------------------------------
def is_spam(text: str) -> bool:
    """Spam requires >=2 distinct spam signals."""
    seen = set()
    for m in RE_SPAM_SIGNAL.finditer(text):
        seen.add(m.group(0).lower())
        if len(seen) >= 2:
            return True
    return False


def detect_injection(text: str) -> Tuple[bool, str]:
    m = RE_INJECT.search(text)
    if m:
        phrase = re.sub(r"\s+", " ", m.group(0)).strip()[:60]
        return True, f"prompt-injection phrase: '{phrase}'"
    return False, ""


def should_force_escalate(subject: str, body: str) -> Tuple[bool, str]:
    """High-risk signals -> (True, reason). RUNS BEFORE the spam shortcut."""
    t = f"{subject} {body}"
    inj, inj_reason = detect_injection(t)
    if inj:
        return True, inj_reason
    if RE_REFUND500.search(t):
        return True, "refund amount over threshold; refunds are never auto-approved"
    if RE_DISPUTE.search(t):
        return True, "chargeback/dispute; escalates to human per policy"
    if RE_LEGAL.search(t):
        return True, "legal content; escalates to human per policy"
    if RE_BREACH.search(t):
        return True, "security breach/compromise; escalates to human"
    if RE_LEAK.search(t):
        return True, "data leak; escalates to human"
    if RE_SSN.search(t):
        return True, "sensitive data (ssn) mentioned; escalates to human"
    if RE_PAYBLOCK.search(t):
        return True, "payment blocked/cannot pay; high priority per policy"
    if RE_OUTAGE.search(t):
        return True, "outage: app/site/service is down; high priority per policy"
    if RE_ANGRY.search(t):
        return True, "angry customer; escalates to human per policy"
    return False, ""


def is_blocking_bug(text: str) -> bool:
    return bool(RE_BLOCKING_BUG.search(text))


def classify_regex(email: Email) -> str:
    """Deterministic fallback classifier. Returns one of CATEGORIES."""
    subj, body = email.subject, email.body
    t = f"{subj} {body}"
    if t.strip() == "":
        return "other"
    if is_spam(t):
        return "spam"
    if RE_BILLING.search(t):
        return "billing"
    if RE_BUG.search(t):
        return "bug_report"
    if RE_FEAT.search(t):
        return "feature_request"
    return "other"


def decide(email: Email, cat: str) -> Triage:
    subj, body = email.subject, email.body
    t = f"{subj} {body}"

    # 1) Forced escalation runs BEFORE the spam shortcut (policy: high-risk
    #    signals cannot be hidden behind a spam label).
    forced, freason = should_force_escalate(subj, body)
    if forced:
        c = cat if cat in CATEGORIES else "other"
        return Triage(
            id=email.id,
            category=c,
            priority="high",
            action="escalate_to_human",
            reply_draft="",
            reason=f"high priority: {freason}; escalating to human.",
        )
    if t.strip() == "":
        return Triage(
            id=email.id,
            category="other",
            priority="medium",
            action="escalate_to_human",
            reply_draft="",
            reason="empty email content; cannot triage; escalating to human for review.",
        )
    if cat == "spam":
        return Triage(
            id=email.id,
            category="spam",
            priority="low",
            action="ignore",
            reply_draft="",
            reason="spam: multiple spam signals; ignoring per policy.",
        )
    if cat == "bug_report":
        if is_blocking_bug(t):
            return Triage(
                id=email.id,
                category="bug_report",
                priority="high",
                action="escalate_to_human",
                reply_draft="",
                reason="high priority: functional bug blocking use; escalating to human.",
            )
        return Triage(
            id=email.id,
            category="bug_report",
            priority="medium",
            action="reply",
            reply_draft="Thanks for the report. We're looking into it and will follow up. If you can share your device and the steps to reproduce, it will help us resolve it faster. — The Support Team",
            reason="medium priority: bug with workaround; replying.",
        )
    if cat == "billing":
        return Triage(
            id=email.id,
            category="billing",
            priority="medium",
            action="reply",
            reply_draft="Thanks for flagging this. We're reviewing your account and will confirm the next step shortly. Could you share the invoice or charge date from your statement? — The Support Team",
            reason="billing issue with an actionable request; replying.",
        )
    if cat == "feature_request":
        return Triage(
            id=email.id,
            category="feature_request",
            priority="low",
            action="reply",
            reply_draft="Thanks for the suggestion. We've logged it for the product team and will reach out if we need more detail. — The Support Team",
            reason="feature request; replying with acknowledgement.",
        )
    if RE_THANKS.search(t) or RE_NONACTION.search(t):
        return Triage(
            id=email.id,
            category="other",
            priority="low",
            action="ignore",
            reply_draft="",
            reason="non-actionable message; ignoring.",
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


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
def classify_email(email: Email) -> str:
    """Current deterministic classifier (LLM wiring lands in Step B)."""
    return classify_regex(email)


def triage_email(email: Email) -> Triage:
    cat = classify_email(email)
    t = decide(email, cat)
    validate_triage(t)
    return t


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
                out.append(triage_email(e))
            except Exception:
                out.append(
                    Triage(
                        id=e.id,
                        category="other",
                        priority="high",
                        action="escalate_to_human",
                        reply_draft="",
                        reason="failed to triage; escalating to human.",
                    )
                )
        write_results(args.output, out)
        print(f"Wrote {len(out)} rows to {args.output}", file=sys.stderr)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()