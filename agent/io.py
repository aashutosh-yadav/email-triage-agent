from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

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
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(
                Email(
                    id=(row.get("id") or "").strip(),
                    sender=(row.get("sender") or "").strip(),
                    subject=(row.get("subject") or "").strip(),
                    body=(row.get("body") or "").strip(),
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
