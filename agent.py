from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from agent_llm import GrogError, GroqClient
except Exception:  # pragma: no cover — keep the batch runnable even if LLM dep breaks
    GrogError = RuntimeError
    GroqClient = None  # type: ignore[assignment]

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
# A "hardsign" token (previous/your/above/system/...) must follow the verb, so
# benign talk like "disregard the earlier instructions I sent" does not fire,
# while canonical attacks ("ignore previous/your instructions") still do.
# --------------------------------------------------------------------------
RE_INJECT = re.compile(
    r"\b(?:"
    r"(?:ignore|disregard|forget|overrule|override)\s+(?:all\s+|any\s+|the\s+|my\s+)*"
    r"(?:your\s+|previous\s+|prior\s+|above\s+|system\s+|developer\s+)"
    r"(?:instructions?|rules?|prompts?|guidelines?)"
    r"|ignore\s+(?:all\s+|any\s+|the\s+)?(?:above|previous|prior)\s+(?:text|content|instructions?)"
    r"|(?:system|developer)\s+prompt"
    r"|reveal\s+(?:your\s+|the\s+)?(?:system\s+)?prompt"
    r"|print\s+(?:your|the)\s+instructions"
    r"|output\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions)"
    r"|jailbreak"
    r"|you\s+are\s+now\s+(?:an?\s+)?(?:admin|assistant|ai)"
    r"|i\s+am\s+(?:the\s+|your\s+)?(?:admin|developer)"
    r"|i['\u2019]m\s+(?:the\s+|your\s+)?(?:admin|developer)"
    r"|mark\s+(?:this|me|this\s+email|this\s+message)\s+as\s+(?:not\s+)?(?:spam|safe|reply)"
    r"|classify\s+(?:me|this|this\s+email)\s+as\s+(?:not\s+)?(?:spam|safe|reply)"
    r")\b",
    re.I,
)

# Forced escalation signals (high risk -> escalate_to_human).
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

# Refund-over-threshold detection: parse only the amount attached to "refund".
RE_REFUND_CTX = re.compile(r"\brefund\w*\b", re.I)
RE_MONEY = re.compile(r"(?:\$\s*(\d[\d,]*(?:\.\d+)?)|\b(\d[\d,]*(?:\.\d+)?)\s*(?:dollars|usd)\b)", re.I)
_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000,
}
_NUM_RUN = re.compile(
    r"(?:" + "|".join(sorted(_WORD_NUM, key=len, reverse=True)) + r")"
    r"(?:\s+(?:and\s+)?" + "(?:" + "|".join(sorted(_WORD_NUM, key=len, reverse=True)) + r"))*"
    r"\s*(?:dollars|usd)\b",
    re.I,
)


def _parse_word_run(span: str) -> float:
    """Value of a number-word span such as 'five hundred dollars' (500.0)."""
    total = 0.0
    current = 0.0
    for w in re.findall(r"[a-z]+", span.lower()):
        v = _WORD_NUM.get(w)
        if v is None:
            continue
        if v == 100:
            current = (current or 1) * 100
        elif v == 1000:
            total += (current or 1) * 1000
            current = 0.0
        else:
            current += v
    return total + current


def _amount_spans(text: str) -> List[Tuple[float, int]]:
    """Every money figure as (value, start_index)."""
    spans: List[Tuple[float, int]] = []
    for m in RE_MONEY.finditer(text):
        raw = (m.group(1) or m.group(2) or "").replace(",", "")
        try:
            spans.append((float(raw), m.start()))
        except ValueError:
            pass
    for m in _NUM_RUN.finditer(text):
        spans.append((_parse_word_run(m.group(0)), m.start()))
    return spans


def _sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()]


def refund_over_threshold(text: str, threshold: float = 500.0) -> bool:
    """True if a refund mention has an attached amount >= the threshold.

    Only the amount NEAREST to the word "refund" counts, so "please refund the
    $10 overcharge from my $600 invoice" is a $10 refund (no escalation), not a
    $600 one. "refund over/above $X" escalates at >= the threshold.
    """
    for sent in _sentences(text):
        if not RE_REFUND_CTX.search(sent):
            continue
        spans = _amount_spans(sent)
        if not spans:
            continue
        considered = [
            min(spans, key=lambda sp: abs(sp[1] - rmatch.start()))[0]
            for rmatch in RE_REFUND_CTX.finditer(sent)
        ]
        over_flag = bool(re.search(r"\b(?:over|above|more\s+than)\b", sent, re.I))
        if any(a > threshold for a in considered) or (
            over_flag and any(a >= threshold for a in considered)
        ):
            return True
    return False

# Category regexes (regex fallback classifier).
RE_BILLING = re.compile(
    r"\b(charg\w*|bill\w*|invoice|payment|billing|refund|subscription|subscribe|credit|debit|price|pricing"
    r"|(?:pro|basic|premium|enterprise|annual|monthly|family|team|business)\s+plan"
    r"|plan\s+(?:price|cost|fee|changes?)"
    r"|(?:upgrade|downgrade|cancel|change)\s+(?:my\s+|the\s+)?plan)\b",
    re.I,
)
RE_BUG = re.compile(
    r"\b(crash\w*|error\w*|broken|bug\w*|not\s+working|not\s+responding|doesn['\u2019]t\s+work|does\s+not\s+work"
    r"|does\s+nothing|glitch|freez\w*"
    r"|fail(?:s|ed|ing|ure)?\s+to\s+(?:launch|load|open|start|run|work|log\s+in)"
    r"|(?:problem|issue)\s+with\s+(?:the\s+)?(?:app|application|login|loading|sync|export(?:ing)?|payments?|billing|invoice|feature|dashboard|notifications?)"
    r"|(?:app|application|site|website|platform|service|feature|dashboard|loading)\s+(?:is|are|has|got)\s+(?:gotten\s+|been\s+)?slow(?:ly|er)?"
    r"|perf\w*\s+(?:has|have)?\s*slowed|slowed\s+down|slow(?:ly)?\s+to\s+(?:load|respond|open)"
    r"|(?:app|application|loading|sync|export|video|network|streaming)\s+lag(?:ging)?|lag(?:ging)?\s+in\s+(?:loading|sync|export)"
    r"|ne\s+fonctionne\s+(?:pas|plus)|fonctionne\s+(?:pas|plus)|ca\s+marche\s+pas"
    r"|(?:app|site|website|platform|service)\s+(?:is|are|was)\s+down|down\s+for\s+everyone"
    r"|(?:50[0348])\s+error|internal\s+server\s+error|outage|won['\u2019]t\s+load"
    r"|data\s+loss|(?:data|files?|records?)\s+(?:was|were)\s+(?:lost|wiped)"
    r"|lost\s+(?:all\s+)?my\s+(?:data|files?))\b",
    re.I,
)
RE_FEAT = re.compile(
    r"\b(feature|integration|suggestion|enhancement|roadmap|please\s+add|could\s+you\s+add|can\s+you\s+add"
    r"|can\s+we\s+(?:have|get)|would\s+be\s+(?:great|nice)\s+to\s+have|would\s+love)\b",
    re.I,
)
RE_THANKS = re.compile(r"\b(thanks|thank\s+you|thx|appreciate\s+it|great\s+job|well\s+done|gracias|merci|danke)\b", re.I)
RE_QUESTION = re.compile(
    r"\b(how\s+do\s+i|how\s+can\s+i|what\s+is|can\s+you|could\s+you|would\s+you|is\s+it\s+possible"
    r"|question|pregunt\w+|qui\s?estion|frage|ask(?:ing)?\s+(?:you|about))\b|\?",
    re.I,
)
RE_NONACTION = re.compile(
    r"\b(no\s+action\s+needed|no\s+reply\s+needed|just\s+fyi|fyi\b|for\s+your\s+information|noted"
    r"|roundup|newsletter|weekly\s+(?:update|roundup)|won\s+a\s+prize|giveaway|product\s+tips"
    r"|heads\s+up|out\s+of\s+office"
    r"|automat(?:ic|ed)\s+(?:reply|response|notification|email|message)|this\s+is\s+an\s+automated"
    r"|do\s+not\s+reply|auto-?reply)\b",
    re.I,
)

# Blocking bugs (no workaround) -> escalate; otherwise bug_with_workaround -> reply.
RE_BLOCKING_BUG = re.compile(
    r"\b(crash\w*|won['\u2019]t\s+(open|start|load|launch|work|cancel)|cannot\s+log\s+in|can['\u2019]t\s+log\s+in"
    r"|black\s+screen|ecran\s+noir|frozen|freez\w*|completely\s+(broken|blocked|unusable)|data\s+loss|locked\s+out"
    r"|unable\s+to\s+(open|access|use)|impossible\s+to\s+(use|open)|lost\s+my\s+data|rien\s+faire|no\s+puedo"
    r"|(?:data|files?|records?|projects?)\s+(?:was|were|is|are)\s+(?:lost|wiped))",
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


def write_log(path: str | Path, rows: Iterable[Dict]) -> None:
    """Append-only decision trail: which classifier produced each row."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


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


def should_force_escalate_detail(subject: str, body: str) -> Tuple[bool, str, str]:
    """High-risk signals -> (True, reason, priority). RUNS BEFORE the spam shortcut."""
    t = f"{subject} {body}"
    inj, inj_reason = detect_injection(t)
    if inj:
        return True, inj_reason, "high"
    if refund_over_threshold(t):
        return True, "refund amount over threshold; refunds are never auto-approved", "medium"
    if RE_DISPUTE.search(t):
        return True, "chargeback/dispute; escalates to human per policy", "high"
    if RE_LEGAL.search(t):
        return True, "legal content; escalates to human per policy", "high"
    if RE_BREACH.search(t):
        return True, "security breach/compromise; escalates to human", "high"
    if RE_LEAK.search(t):
        return True, "data leak; escalates to human", "high"
    if RE_SSN.search(t):
        return True, "sensitive data (ssn) mentioned; escalates to human", "high"
    if RE_PAYBLOCK.search(t):
        return True, "payment blocked/cannot pay; high priority per policy", "high"
    if RE_OUTAGE.search(t):
        return True, "outage: app/site/service is down; high priority per policy", "high"
    if RE_ANGRY.search(t):
        return True, "angry customer; escalates to human per policy", "medium"
    return False, "", ""


def should_force_escalate(subject: str, body: str) -> Tuple[bool, str]:
    """Public 2-tuple API: (escalate?, reason)."""
    forced, reason, _ = should_force_escalate_detail(subject, body)
    return forced, reason


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
    forced, freason, fprio = should_force_escalate_detail(subj, body)
    if forced:
        c = cat if cat in CATEGORIES else "other"
        prio_prefix = "high priority" if fprio == "high" else "medium priority"
        return Triage(
            id=email.id,
            category=c,
            priority=fprio,
            action="escalate_to_human",
            reply_draft="",
            reason=f"{prio_prefix}: {freason}; escalating to human.",
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
    if RE_NONACTION.search(t):
        return Triage(
            id=email.id,
            category="other",
            priority="low",
            action="ignore",
            reply_draft="",
            reason="non-actionable message (notification/auto-reply/OoO); ignoring.",
        )
    if RE_QUESTION.search(t):
        return Triage(
            id=email.id,
            category="other",
            priority="low",
            action="reply",
            reply_draft="Thanks for reaching out. We'll get back to you shortly. — The Support Team",
            reason="general inquiry; acknowledging.",
        )
    if RE_THANKS.search(t):
        return Triage(
            id=email.id,
            category="other",
            priority="low",
            action="ignore",
            reply_draft="",
            reason="non-actionable message (thanks/appreciation); ignoring.",
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
def classify_email(
    email: Email,
    use_llm: bool = False,
    client: Optional[GroqClient] = None,
) -> Tuple[str, str, str, Optional[str]]:
    """Classify one email.

    Returns (category, source, rationale, raw_llm_content) where source is
    'llm' when the Groq model produced a valid category, else 'fallback' (regex).
    The batch never crashes: any LLM failure falls back to the regex classifier.
    """
    if use_llm and client is not None:
        try:
            cat, rationale, raw = client.propose_category(email)
            if cat in CATEGORIES:
                return cat, "llm", rationale, (raw or "")[:500]
        except Exception:
            pass  # retry is handled inside the client; any residual failure -> fallback
    return classify_regex(email), "fallback", "", None


def triage_email(
    email: Email,
    use_llm: bool = False,
    client: Optional[GroqClient] = None,
) -> Tuple[Triage, Dict]:
    """Triage one email; never raises for row-level issues."""
    cat, source, rationale, raw = classify_email(email, use_llm=use_llm, client=client)
    try:
        t = decide(email, cat)
        validate_triage(t)
        return t, {"id": email.id, "source": source, "category": t.category,
                   "priority": t.priority, "action": t.action, "reason": t.reason,
                   "rationale": rationale, "raw_llm": raw}
    except Exception as exc:
        t = Triage(
            id=email.id,
            category="other",
            priority="high",
            action="escalate_to_human",
            reply_draft="",
            reason="failed to triage; escalating to human.",
        )
        return t, {"id": email.id, "source": source, "category": t.category,
                   "priority": t.priority, "action": t.action, "reason": t.reason,
                   "rationale": rationale, "raw_llm": raw, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(prog="triage")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log", default="out/decision_log.jsonl",
                        help="decision trail (append-only); default out/decision_log.jsonl")
    parser.add_argument("--no-llm", action="store_true",
                        help="deterministic run: use the regex classifier only")
    args = parser.parse_args()

    use_llm = (not args.no_llm) and GroqClient is not None
    client: Optional[GroqClient] = None
    if use_llm:
        try:
            client = GroqClient()
        except Exception as exc:
            print(f"warning: could not init LLM client ({exc}); using regex only", file=sys.stderr)
            client = None

    try:
        emails = read_emails(args.input)
        out: List[Triage] = []
        log_rows: List[Dict] = []
        for e in emails:
            t, info = triage_email(e, use_llm=client is not None, client=client)
            out.append(t)
            log_rows.append(info)
        write_log(args.log, log_rows)
        # results.csv is written LAST so a failed decision-log write cannot
        # leave a valid-looking output file behind.
        write_results(args.output, out)
        counts = {s: sum(1 for r in log_rows if r.get("source") == s) for s in ("llm", "fallback")}
        print(f"Wrote {len(out)} rows to {args.output} (llm={counts['llm']}, fallback={counts['fallback']})", file=sys.stderr)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()