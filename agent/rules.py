from __future__ import annotations

CATEGORIES = {"billing", "bug_report", "feature_request", "spam", "other"}
PRIORITIES = {"high", "medium", "low"}
ACTIONS = {"reply", "escalate_to_human", "ignore"}


def is_empty(s: str | None) -> bool:
    return not s or not s.strip()
