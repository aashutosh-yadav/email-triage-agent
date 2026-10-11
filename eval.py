from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--expected", required=True)
    p.add_argument("--predicted", required=True)
    args = p.parse_args()

    exp = {r["id"]: r for r in csv.DictReader(Path(args.expected).open())}
    pred = {r["id"]: r for r in csv.DictReader(Path(args.predicted).open())}

    keys = sorted(set(exp) & set(pred))
    if not keys:
        print("no overlapping ids")
        return

    def score(field: str) -> float:
        ok = 0
        for k in keys:
            if exp[k].get(field) == pred[k].get(field):
                ok += 1
        return ok / len(keys) * 100.0

    print("ids:", len(keys))
    print(f"category: {score('category'):.1f}%")
    print(f"priority: {score('priority'):.1f}%")
    print(f"action: {score('action'):.1f}%")


if __name__ == "__main__":
    main()
