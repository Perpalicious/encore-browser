"""
Fan a deduplicated resale valuation back out to every lot in the auction.

    python3 tools/expand_resale.py <ID>

Reads  data/categorized/auction_<ID>_resale_deduped.json  (from the ChatGPT pass)
       data/categorized/auction_<ID>_resale_groups.json   (from slim_resale.py)
Writes data/categorized/auction_<ID>_resale.json          (what `build` consumes)

The resale pass values one representative per distinct product. Each valuation
is copied verbatim to every lot in that product's group, so the file `build`
sees looks exactly as though every lot were valued individually.

Fails loudly on a short input. The resale join in `build/resale.py` is lenient
by design — an unvalued lot simply keeps null and the build neither warns nor
errors — so a truncated ChatGPT run would otherwise sail through and produce a
site quietly missing most of its resale data. Coverage is checked here instead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Fields carried from the representative's valuation onto every group member.
RESALE_FIELDS = [
    "est_resale_low",
    "est_resale_high",
    "resale_confidence",
    "resale_outlook",
    "reasoning",
]


def load_items(path: Path, label: str) -> list[dict]:
    if not path.exists():
        sys.exit(f"Error: {label} not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    sys.exit(f"Error: {label} must be a JSON array or an object with 'items'.")


def main(auction_id: str) -> None:
    valued = load_items(
        Path(f"data/categorized/auction_{auction_id}_resale_deduped.json"),
        "deduped resale file",
    )
    groups_path = Path(f"data/categorized/auction_{auction_id}_resale_groups.json")
    if not groups_path.exists():
        sys.exit(f"Error: group map not found: {groups_path}. Run tools/slim_resale.py.")
    groups: dict[str, list[str]] = json.loads(groups_path.read_text(encoding="utf-8"))

    by_rep = {str(v.get("lot_number") or "").strip(): v for v in valued}

    expanded: list[dict] = []
    missing: list[str] = []
    unknown = [k for k in by_rep if k not in groups]

    for rep_lot, members in groups.items():
        valuation = by_rep.get(rep_lot)
        if valuation is None:
            missing.append(rep_lot)
            continue
        for lot_number in members:
            row = {"lot_number": lot_number}
            for field in RESALE_FIELDS:
                if valuation.get(field) is not None:
                    row[field] = valuation[field]
            expanded.append(row)

    total_lots = sum(len(v) for v in groups.values())
    print(f"{len(valued)} valuations -> {len(expanded)} lots "
          f"({100 * len(expanded) / total_lots:.1f}% of {total_lots})")

    if unknown:
        print(f"  WARNING: {len(unknown)} valuations had a lot_number not in the "
              f"group map and were ignored. First few: {unknown[:5]}", file=sys.stderr)

    if missing:
        lost = sum(len(groups[k]) for k in missing)
        sys.exit(
            f"\nError: {len(missing)} of {len(groups)} products were never valued, "
            f"covering {lost} lots ({100 * lost / total_lots:.1f}% of the auction).\n"
            f"The ChatGPT pass almost certainly truncated. Re-run it for the missing "
            f"products and merge the results before continuing.\n"
            f"First few unvalued representative lot_numbers: {missing[:10]}"
        )

    out = Path(f"data/categorized/auction_{auction_id}_resale.json")
    out.write_text(json.dumps(expanded), encoding="utf-8")
    print(f"  wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
