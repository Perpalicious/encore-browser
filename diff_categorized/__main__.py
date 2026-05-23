"""
CLI: extract uncategorized lots from a raw scrape.

Usage:
    python -m diff_categorized \\
        --raw      data/raw/auction_<id>.json \\
        --existing data/categorized/auction_<id>_categorized.json \\
        --output   data/categorized/auction_<id>_to_categorize.json

The output JSON has the same envelope shape as the raw scrape
(``{auction_id, auction_name, scraped_at, item_count, items: [...]}``) so it
can be dropped into the Auction Agent for incremental categorization.

A lot is considered "already categorized" if either ``str(raw["id"])`` or
``raw["lot_number"]`` appears as a ``lot_number`` value in the existing
categorized file. (The Auction Agent's ``lot_number`` field has, in observed
samples, held the HiBid numeric id rather than the display lot number, so we
check both.)

Exits non-zero with a friendly message when there is nothing to do.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_items(path: Path, label: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Return (items, envelope). ``envelope`` is the surrounding object (without
    its ``items`` key) when the file is a dict; otherwise ``{}``.
    """
    if not path.exists():
        print(f"Error: {label} file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data, {}
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        envelope = {k: v for k, v in data.items() if k != "items"}
        return list(data["items"]), envelope
    print(
        f"Error: {label} JSON must be a list or have an 'items' list; "
        f"got {type(data).__name__}.",
        file=sys.stderr,
    )
    sys.exit(1)


def _categorized_key_set(categorized_items: list[dict[str, Any]]) -> set[str]:
    """All ``lot_number`` values present in the existing categorized file."""
    keys: set[str] = set()
    for item in categorized_items:
        ln = item.get("lot_number")
        if ln is not None and ln != "":
            keys.add(str(ln))
    return keys


def _raw_keys(raw_item: dict[str, Any]) -> tuple[str, str]:
    """The two candidate join keys for one raw item: (id-as-string, lot_number)."""
    rid = raw_item.get("id")
    rid_str = str(rid) if rid is not None else ""
    ln = raw_item.get("lot_number")
    ln_str = str(ln) if ln is not None else ""
    return rid_str, ln_str


def diff(
    raw_items: list[dict[str, Any]],
    existing_categorized_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pure function: return the raw items not yet present in categorized."""
    categorized_keys = _categorized_key_set(existing_categorized_items)
    new: list[dict[str, Any]] = []
    for item in raw_items:
        rid_str, ln_str = _raw_keys(item)
        if rid_str and rid_str in categorized_keys:
            continue
        if ln_str and ln_str in categorized_keys:
            continue
        new.append(item)
    return new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m diff_categorized",
        description=(
            "Extract lots present in a raw scrape but not yet in the "
            "categorized JSON, for incremental categorization."
        ),
    )
    parser.add_argument("--raw", required=True, metavar="PATH")
    parser.add_argument("--existing", required=True, metavar="PATH")
    parser.add_argument("--output", required=True, metavar="PATH")
    args = parser.parse_args(argv)

    raw_path = Path(args.raw)
    existing_path = Path(args.existing)
    output_path = Path(args.output)

    raw_items, raw_envelope = _load_items(raw_path, "raw")
    existing_items, _ = _load_items(existing_path, "existing")

    new_items = diff(raw_items, existing_items)

    print(
        f"Found {len(new_items)} new lots out of {len(raw_items)} total raw, "
        f"{len(existing_items)} existing categorized."
    )

    if not new_items:
        print(
            "Nothing to do: every raw lot is already present in the existing "
            "categorized file. If you want to fully recategorize, send the raw "
            "file directly to the Auction Agent and overwrite the categorized "
            "file when it returns.",
            file=sys.stderr,
        )
        return 1

    out = dict(raw_envelope)
    out["item_count"] = len(new_items)
    out["items"] = new_items

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Wrote {len(new_items)} lots to {output_path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
