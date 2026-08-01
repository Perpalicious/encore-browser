"""
Collapse the slimmed file to one row per distinct product for the resale pass.

    python3 tools/slim_resale.py <ID>

Reads  data/categorized/auction_<ID>_for_agent.json
Writes data/categorized/auction_<ID>_for_resale.json      (the agent's input)
       data/categorized/auction_<ID>_resale_groups.json   (fan-out map)

Why
---
These auctions list the same product many times over — 58 identical Nintendo
cases, 50 identical boxes of Tide Pods. Valuing each copy separately spends
output budget to re-derive an answer we already have, and invites the agent to
give the same item different numbers in different chunks.

This is deliberately NOT junk filtering. Rule-based "this lot is worthless"
guesses measured badly on real data: the lots that look structurally worthless
(damaged + missing parts + non-functional) number in the dozens, and include
things like a Samsung monitor and a Canon printer that plausibly carry parts
value. Dedup needs no judgment call and loses no coverage — every lot still
ends up valued, via `tools/expand_resale.py`.

Grouping
--------
The key is every field that can change what a lot is worth: title, model,
size, condition, the damage/missing-parts free text, and the three condition
flags. Two lots share a valuation only when all of those match exactly, so a
sealed unit is never averaged together with a broken one.

Matching is exact, not fuzzy. Near-miss titles stay separate — that costs some
redundancy but can never merge two genuinely different products.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Every field that can move the price. Title is handled separately.
VALUE_FIELDS = [
    "model",
    "size",
    "condition",
    "notes",
    "damage",
    "missing_parts",
    "damaged",
    "missing_major_parts",
    "functional",
]


def group_key(rec: dict) -> tuple:
    return (rec.get("title", "").strip().upper(),) + tuple(
        str(rec.get(f, "")).strip().upper() for f in VALUE_FIELDS
    )


def main(auction_id: str) -> None:
    src = Path(f"data/categorized/auction_{auction_id}_for_agent.json")
    out_items = Path(f"data/categorized/auction_{auction_id}_for_resale.json")
    out_groups = Path(f"data/categorized/auction_{auction_id}_resale_groups.json")

    if not src.exists():
        sys.exit(f"Error: slimmed file not found: {src}. Run tools/slim.py first.")

    slim = json.loads(src.read_text(encoding="utf-8"))

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for rec in slim:
        groups[group_key(rec)].append(rec)

    representatives = []
    fan_out: dict[str, list[str]] = {}
    for members in groups.values():
        # Stable representative so re-running produces an identical file.
        members = sorted(members, key=lambda r: str(r.get("lot_number")))
        rep = dict(members[0])
        # How many identical lots are in this auction. Real signal for a
        # flipper: 58 copies of one item is a saturated local market. Delete
        # this line (and the prompt's mention of it) to value in isolation.
        rep["qty"] = len(members)
        representatives.append(rep)
        fan_out[str(rep["lot_number"])] = [str(m["lot_number"]) for m in members]

    out_items.write_text(json.dumps(representatives), encoding="utf-8")
    out_groups.write_text(json.dumps(fan_out), encoding="utf-8")

    covered = sum(len(v) for v in fan_out.values())
    if covered != len(slim):
        sys.exit(f"Error: fan-out covers {covered} lots but input had {len(slim)}")

    saved = len(slim) - len(representatives)
    print(f"{len(slim)} lots -> {len(representatives)} distinct products")
    print(f"  {saved} rows saved ({100 * saved / len(slim):.1f}% fewer)")
    print(f"  groups of 2+: {sum(1 for v in fan_out.values() if len(v) > 1)}")
    print(f"  largest group: {max(len(v) for v in fan_out.values())} lots")
    print(f"  wrote {out_items}")
    print(f"  wrote {out_groups}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
