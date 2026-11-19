"""Measure how well the parser understands questions.

    python -m app.search.evaluate                    # the held-out test set
    python -m app.search.evaluate --set dev          # the set used while improving rules
    python -m app.search.evaluate --set dev --misses # list every miss

Each line of tests/data/search_<set>.jsonl has a question, the date it's
asked on, and the intent a person would expect. Both the parser's answer and
the expected intent go through normalize_intent, as they do in the app, and
then every field is compared.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path

from app.search.intent import SearchIntent, normalize_intent
from app.search.rules import parse_rules


DATA_DIR = Path(__file__).resolve().parents[2] / "tests" / "data"
FIELDS = ("mode", "places", "date", "month", "forecast_days", "units", "metric",
          "condition", "months", "region", "limit")


def comparable(intent: SearchIntent, today: date) -> dict:
    data = normalize_intent(intent, today).model_dump(mode="json")
    # "St. Louis" and "st louis" are the same answer.
    data["places"] = [" ".join(p.lower().replace(".", "").replace(",", " ").split())
                      for p in data["places"]]
    return {field: data[field] for field in FIELDS}


def evaluate(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    field_hits: Counter = Counter()
    by_category: dict[str, list[bool]] = defaultdict(list)
    misses = []
    for row in rows:
        today = date.fromisoformat(row["today"])
        expected = comparable(SearchIntent.model_validate(row["intent"]), today)
        got = comparable(parse_rules(row["query"], today), today)
        wrong = {f: {"got": got[f], "expected": expected[f]} for f in FIELDS if got[f] != expected[f]}
        field_hits.update(f for f in FIELDS if f not in wrong)
        by_category[row["category"]].append(not wrong)
        if wrong:
            misses.append({"query": row["query"], "wrong": wrong})
    total = len(rows)
    return {
        "questions": total,
        "exact": total - len(misses),
        "fields": {f: field_hits[f] / total for f in FIELDS},
        "categories": {c: (sum(r), len(r)) for c, r in sorted(by_category.items())},
        "misses": misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the natural-language parser.")
    parser.add_argument("--set", choices=["test", "dev"], default="test")
    parser.add_argument("--misses", action="store_true", help="list every question it got wrong")
    args = parser.parse_args()

    result = evaluate(DATA_DIR / f"search_{args.set}.jsonl")
    total = result["questions"]
    print(f"{args.set} set: {result['exact']}/{total} questions fully correct "
          f"({result['exact'] / total:.0%})\n")
    print("By category:")
    for category, (right, count) in result["categories"].items():
        print(f"  {category:<11} {right}/{count}")
    print("\nBy field:")
    for field, accuracy in result["fields"].items():
        print(f"  {field:<14} {accuracy:.0%}")
    if args.misses and result["misses"]:
        print("\nMisses:")
        for miss in result["misses"]:
            details = "; ".join(f"{f}: got {v['got']!r}, expected {v['expected']!r}"
                                for f, v in miss["wrong"].items())
            print(f"  {miss['query']!r}\n      {details}")


if __name__ == "__main__":
    main()