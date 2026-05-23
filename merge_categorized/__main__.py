"""
CLI: merge newly categorized lots into the existing categorized file.

Usage:
    python -m merge_categorized \\
        --existing data/categorized/auction_<id>_categorized.json \\
        --new      <path_to_agent_response.json> \\
        --output   data/categorized/auction_<id>_categorized.json

``--output`` may be the same path as ``--existing`` for in-place updates;
the write is atomic (tmp file in the same directory + ``os.replace``) so an
interrupted run cannot corrupt the existing file.

Dedup rule: keys are ``lot_number`` (stringified). If a lot_number appears
in both files, the entry from ``--new`` wins — this allows the user to
re-categorize a previously categorized lot by sending a corrected response.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


def _load_items(path: Path, label: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (items, envelope) — envelope is the dict-shaped wrapper minus 'items'."""
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


def merge(
    existing_items: list[dict[str, Any]], new_items: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Combine existing and new categorized items. Returns
    ``(merged_items, n_added, n_updated)`` where ``n_added`` is the count of
    lots only present in ``new_items`` and ``n_updated`` is the count of lots
    that appeared in both (the new value replaced the existing one).

    Order: the merged list keeps the existing order (preserving any
    user-meaningful ordering already in the file), then appends genuinely-new
    items in the order they appear in ``new_items``.
    """
    # Index new items by lot_number for O(1) lookup, latest write wins
    new_by_key: dict[str, dict[str, Any]] = {}
    for item in new_items:
        ln = item.get("lot_number")
        if ln is not None and ln != "":
            new_by_key[str(ln)] = item

    merged: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    n_updated = 0

    # First pass: walk existing, swap in any new replacement on collision
    for item in existing_items:
        ln = item.get("lot_number")
        key = str(ln) if ln is not None else ""
        if key and key in new_by_key:
            merged.append(new_by_key[key])
            used_keys.add(key)
            n_updated += 1
        else:
            merged.append(item)

    # Second pass: append every new item not already matched
    n_added = 0
    for item in new_items:
        ln = item.get("lot_number")
        key = str(ln) if ln is not None else ""
        if key and key in used_keys:
            continue
        # Items without a usable lot_number are appended as-is (treated as new)
        merged.append(item)
        if key:
            used_keys.add(key)
        n_added += 1

    return merged, n_added, n_updated


def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write ``payload`` to ``path`` via tmp-file + ``os.replace`` so the
    target is never seen half-written. Tmp file lives in the same directory
    as the target so the replace is on the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m merge_categorized",
        description=(
            "Merge newly categorized lots into an existing categorized file. "
            "Dedup by lot_number; new entries override existing ones on "
            "collision (allowing re-categorization corrections)."
        ),
    )
    parser.add_argument("--existing", required=True, metavar="PATH")
    parser.add_argument("--new", required=True, metavar="PATH")
    parser.add_argument("--output", required=True, metavar="PATH")
    args = parser.parse_args(argv)

    existing_path = Path(args.existing)
    new_path = Path(args.new)
    output_path = Path(args.output)

    existing_items, existing_envelope = _load_items(existing_path, "existing")
    new_items, new_envelope = _load_items(new_path, "new")

    merged_items, n_added, n_updated = merge(existing_items, new_items)

    # Preserve existing envelope (auction_id, auction_name, scraped_at, etc).
    # Fall back to the new envelope for fields the existing file didn't set.
    out: dict[str, Any] = dict(new_envelope)
    out.update(existing_envelope)
    out["item_count"] = len(merged_items)
    out["items"] = merged_items

    _atomic_write_json(output_path, out)

    print(
        f"Merged {n_added} new items, {n_updated} updates, "
        f"total now {len(merged_items)} -> {output_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
