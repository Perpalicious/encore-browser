"""
Build the slimmed per-lot file that feeds all three ChatGPT passes.

    python3 tools/slim.py <ID>      # <ID> is e.g. 763293, or "combined"

Reads  data/raw/auction_<ID>.json
Writes data/categorized/auction_<ID>_for_agent.json

Why this isn't a one-liner
--------------------------
HiBid packs every per-lot detail into `description_raw` as \\r-separated
"Key: value" or "Question? answer" lines. The scraper lifts out Est. Retail
Price and Condition, then strips all remaining structured lines from
`description` — which in practice leaves `description` empty for 100% of lots,
because these listings contain no free-form prose at all.

That silently discards fields the valuation and matching passes genuinely
need: `Model` (present on ~79% of lots, often the only way to identify what an
item actually is when the title is a bare SKU), `Verified Size` (~35%),
`Notes` (quantity/usage caveats like "20% USED", occasionally "DO NOT BID"),
and free-text damage / missing-parts descriptions.

The cleaner long-term fix is for the scraper to emit these as first-class
fields so this reparsing goes away. Doing it here avoids a re-scrape.

Token economy
-------------
Every field costs output budget across ~26k lots x 3 passes, so:
  - Keys are omitted entirely when absent or empty (no `null` padding).
  - Yes/No flags are emitted ONLY when the answer is noteworthy. A lot with no
    `damaged` key is undamaged; absence means "nothing to report".
  - `description` is emitted only on the rare lot that actually has prose.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

# "Key: value" lines worth forwarding, mapped to their slim-file names.
TEXT_FIELDS = {
    "Model": "model",
    "Verified Size": "size",
    "Notes": "notes",
    "Damage Desct": "damage",
    "Missing Parts Desc": "missing_parts",
}

# "Question? answer" flags, with the answers worth spending tokens on.
FLAG_FIELDS = {
    "Is Item Damaged?": ("damaged", {"Yes", "Unknown"}),
    "Missing Major Parts?": ("missing_major_parts", {"Yes", "Unknown"}),
    "Is Item Functional?": ("functional", {"No", "Unable to Test"}),
}

_FLAG_RE = re.compile(r"^(.+\?)\s*(.*)$")


def slim_item(item: dict) -> dict:
    """Reduce one raw scrape item to the fields the ChatGPT passes see."""
    rec = {
        "lot_number": item.get("lot_number"),
        "title": item.get("title", ""),
        "est_retail_price": item.get("est_retail_price"),
        "condition": item.get("condition"),
        "category": item.get("hibid_category_path"),
    }

    for line in (item.get("description_raw") or "").split("\r"):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            name = TEXT_FIELDS.get(key.strip())
            if name and value.strip():
                rec[name] = value.strip()
            continue
        match = _FLAG_RE.match(line)
        if match:
            flag = FLAG_FIELDS.get(match.group(1))
            if flag and match.group(2).strip() in flag[1]:
                rec[flag[0]] = match.group(2).strip()

    description = (item.get("description") or "").strip()
    if description:
        rec["description"] = description

    return rec


def main(auction_id: str) -> None:
    src = Path(f"data/raw/auction_{auction_id}.json")
    dst = Path(f"data/categorized/auction_{auction_id}_for_agent.json")

    if not src.exists():
        sys.exit(f"Error: raw file not found: {src}")

    data = json.loads(src.read_text(encoding="utf-8"))
    items = data.get("items", data) if isinstance(data, dict) else data

    slim = [slim_item(i) for i in items]
    dst.write_text(json.dumps(slim), encoding="utf-8")

    print(f"{len(slim)} lots -> {dst}")
    counts = Counter(key for rec in slim for key in rec)
    for key, n in counts.most_common():
        print(f"  {key:20s} {n:>6} ({100 * n / len(slim):.1f}%)")

    missing = [k for k in ("lot_number", "title", "category") if counts[k] != len(slim)]
    if missing:
        sys.exit(f"Error: fields missing on some lots: {missing}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
