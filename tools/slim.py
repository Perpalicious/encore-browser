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

That silently discards fields the passes genuinely need: `Model`, `Verified
Size`, `Notes` (quantity/usage caveats like "20% USED", occasionally "DO NOT
BID"), and free-text damage / missing-parts descriptions.

The cleaner long-term fix is for the scraper to emit these as first-class
fields so this reparsing goes away. Doing it here avoids a re-scrape.

HiBid moved these fields into an image (2026-08-30)
---------------------------------------------------
During the week of 2026-08-30 Encore stopped putting the structured detail in
the listing and started rendering it into a per-lot "LOT SPECIFIC REPORT"
JPEG instead. `description_raw` is now only `Condition: EXCELLENT` — median
length 20 characters across all 25,195 lots of auction 764524, with no `Model:`
or `Size:` marker on any of them.

So `model` (was 77-80%), `size` (33%), `notes`, `damage`, `damaged`,
`missing_major_parts` and `functional` are now 0%, and THAT IS EXPECTED. It is
not a parser break, and this file needs no key-mapping fix. The printout below
says so explicitly rather than leaving a wall of absent fields to interpret.

What that costs, measured against 2026-08-16 (the last week with the fields):
`model` was present on 77% of lots and added text not already in the title on
80% of those — 62% of all lots. But titles that are a bare SKU, the reason
PROMPTS.md gives for wanting `model`, are only 0.3% of lots. The field mattered
for pinning an exact variant (valuation), far less for deciding which bucket
something belongs in (flagging).

The data is recoverable: the report is `additional_images[-1]` on every lot,
already captured by the scraper, and fetchable with curl_cffi plus a Referer
(plain curl returns `{}`). Nobody OCRs it today. If that changes, run it over
flagged lots only — the flags do not need it, and 25k downloads a week to
enrich lots nobody will bid on is a bad trade.

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

    # Absence of the whole structured block means HiBid is rendering it into
    # the lot report image, not that the key mapping broke. Say which, because
    # the two look identical in the coverage table above.
    reparsed = set(TEXT_FIELDS.values()) | {n for n, _ in FLAG_FIELDS.values()}
    if not any(counts[k] for k in reparsed):
        print()
        print("  note: no Model / Verified Size / Notes / damage fields on any lot.")
        print("        Expected since 2026-08-30 — HiBid renders these into the")
        print("        per-lot report image now. Not a parser break; see the")
        print("        docstring. Flagging runs on title + condition + category.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
