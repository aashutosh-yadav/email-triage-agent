from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import agent

FIELDS = ("category", "priority", "action")

Case = Tuple[agent.Email, Dict[str, str]]


def load_cases(path: str) -> List[Case]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cases: List[Case] = []
    for r in rows:
        e = agent.Email(
            id=(r.get("id") or "").strip(),
            sender=(r.get("sender") or "").strip(),
            subject=(r.get("subject") or "").strip(),
            body=(r.get("body") or "").strip()[:10000],
        )
        exp = {field: (r.get("expected_" + field) or "").strip() for field in FIELDS}
        cases.append((e, exp))
    return cases


def load_predicted(path: str) -> Dict[str, Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def main() -> None:
    p = argparse.ArgumentParser(prog="eval")
    p.add_argument("--cases", default="eval_cases.csv")
    p.add_argument("--predicted", default=None,
                   help="score an existing results.csv instead of running the pipeline")
    p.add_argument("--llm", action="store_true",
                   help="use the LLM classifier when GROQ_API_KEY is set (default: deterministic)")
    args = p.parse_args()

    cases = load_cases(args.cases)
    if not cases:
        print("no cases found"); sys.exit(1)

    rows = []
    if args.predicted:
        preds = load_predicted(args.predicted)
        for e, exp in cases:
            pr = preds.get(e.id)
            if pr is None:
                print(f"missing predicted row for id {e.id}"); sys.exit(1)
            rows.append((e, exp, pr))
    else:
        client = agent.GroqClient() if (args.llm and agent.GroqClient is not None) else None
        for e, exp in cases:
            t, _info = agent.triage_email(e, use_llm=client is not None, client=client)
            rows.append((e, exp, {"id": t.id, "category": t.category, "priority": t.priority,
                                  "action": t.action, "reply_draft": t.reply_draft, "reason": t.reason}))

    n = len(rows)
    mismatches: List[Tuple[str, str, str, str]] = []
    for field in FIELDS:
        bad = 0
        for _e, exp, pred in rows:
            if exp[field] != pred[field]:
                bad += 1
                mismatches.append((pred["id"], field, exp[field], pred[field]))
        if n:
            print(f"{field}: {100.0 * (n - bad) / n:.1f}% ({n - bad}/{n})")

    esc = [(e, exp, pred) for e, exp, pred in rows if exp["action"] == "escalate_to_human"]
    if esc:
        ok = sum(1 for _e, exp, pred in esc if pred["action"] == "escalate_to_human")
        print(f"action (escalation rows only): {100.0 * ok / len(esc):.1f}% ({ok}/{len(esc)})")

    for _e, exp, pred in rows:
        if exp["action"] == "reply" and pred["action"] != "reply":
            mismatches.append((pred["id"], "reply_draft(expected reply)", "reply", pred["action"]))

    inv = [pred["id"] for _e, _exp, pred in rows
           if (pred["action"] == "reply") != bool((pred.get("reply_draft") or "").strip())]
    print(f"reply_draft invariant violations: {len(inv)} {inv}")

    if mismatches:
        print("\n--- mismatching rows ---")
        for eid, field, expected, got in sorted(mismatches):
            print(f"{eid}: {field}: expected={expected!r} got={got!r}")
    else:
        print("\nno mismatches")


if __name__ == "__main__":
    main()