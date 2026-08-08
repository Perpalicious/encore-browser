"""
Verify the three ChatGPT pass outputs before anything is merged or built.

    python3 tools/verify_passes.py <ID>

Checks each file for required fields, and — the important part — that its
lot_numbers match this week's slimmed file exactly.

Why the lot-set check matters
-----------------------------
Two-auction weeks all write to `auction_combined_*.json`, so last week's files
sit at exactly the paths this week's build reads. Measured on real data, a
previous week's categorized file shared 93.9% of its lot_numbers with the
following week's auction — because the S-/M- prefixes and lot numbering repeat.

Building against a stale file therefore does not fail. It joins last week's
flags onto this week's different items at the same lot numbers and produces a
complete, plausible, entirely wrong bundle. Row counts alone do not catch it;
comparing the actual lot sets does.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {
    "categorized": {"lot_number", "is_bats_list", "bats_buckets"},
    "resale": {"lot_number", "est_resale_low", "est_resale_high"},
    "personal": {"lot_number", "personal_match"},
}


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise ValueError("expected a JSON array or an object with an 'items' array")


def main(auction_id: str) -> None:
    slim_path = Path(f"data/categorized/auction_{auction_id}_for_agent.json")
    if not slim_path.exists():
        sys.exit(f"Error: slimmed file not found: {slim_path}")
    expected = {str(r["lot_number"]) for r in load(slim_path)}
    print(f"this week's slimmed file: {len(expected)} lots\n")

    failed = False
    for label in ("categorized", "resale", "personal"):
        path = Path(f"data/categorized/auction_{auction_id}_{label}.json")
        if not path.exists():
            print(f"{label:12s} MISSING  {path}")
            failed = True
            continue

        try:
            items = load(path)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"{label:12s} UNREADABLE  {exc}")
            print(f"{'':12s}   (a markdown-wrapped or truncated response looks like this)")
            failed = True
            continue

        if not items:
            print(f"{label:12s} EMPTY")
            failed = True
            continue

        problems = []
        fields = set(items[0].keys())
        missing_fields = REQUIRED[label] - fields
        if missing_fields:
            problems.append(f"missing fields {sorted(missing_fields)}")

        lots = {str(r.get("lot_number")) for r in items}
        dupes = len(items) - len(lots)
        if dupes:
            problems.append(f"{dupes} duplicate lot_numbers")

        unknown = lots - expected
        absent = expected - lots
        if unknown:
            problems.append(
                f"{len(unknown)} lot_numbers not in this week's auction "
                f"(e.g. {sorted(unknown)[:3]}) — likely a stale file"
            )
        # Only the categorized pass strictly must cover every lot: it decides
        # which lots exist in the bundle at all. The others are joins.
        if absent:
            pct = 100 * len(absent) / len(expected)
            note = f"{len(absent)} lots absent ({pct:.1f}%)"
            problems.append(note if label == "categorized" else note + " — expected only if the pass skipped lots")

        status = "FAIL" if problems and (unknown or missing_fields or dupes or (absent and label == "categorized")) else "ok  "
        if status == "FAIL":
            failed = True
        print(f"{label:12s} {status}  {len(items)} rows, {len(lots)} distinct lots")
        for p in problems:
            print(f"{'':12s}   - {p}")

        # Bat's List subtypes are the drill-down's third level. They are
        # optional (an older file has none), so this reports rather than fails
        # — but a pass that ignored the instruction, or that invented a new
        # phrasing per lot, is only visible here. Both are cheap to catch now
        # and expensive to notice after the bundle is built.
        if label == "categorized":
            flagged = [r for r in items if r.get("is_bats_list")]
            if flagged:
                subtypes = [
                    " ".join(str(r["bats_subtype"]).split()).lower()
                    for r in flagged
                    if r.get("bats_subtype")
                ]
                pct = 100 * len(subtypes) / len(flagged)
                distinct = len(set(subtypes))
                print(
                    f"{'':12s}   subtypes: {len(subtypes)}/{len(flagged)} flagged lots "
                    f"({pct:.0f}%), {distinct} distinct"
                )
                if not subtypes:
                    print(f"{'':12s}   - no bats_subtype at all; the drill-down keeps two levels")
                elif distinct > max(40, len(subtypes) // 4):
                    print(
                        f"{'':12s}   - {distinct} distinct subtypes for {len(subtypes)} lots "
                        f"reads as per-lot phrasing rather than reused wording"
                    )

    print()
    if failed:
        sys.exit("VERIFY FAILED — do not build. Fix the files above and re-run.")
    print("All three files verified against this week's lot set.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
