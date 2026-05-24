"""
CLI entry point: join a raw scrape with the Auction Agent's categorized
output, then validate and write the viewer bundle.

Usage
-----
    python -m build \\
        --raw         data/raw/auction_741675.json \\
        --categorized data/categorized/auction_741675_categorized.json \\
        --output      viewer/src/data/auction_bundle.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any


def _load_items(path: Path, label: str) -> list[dict[str, Any]]:
    """Accept either a bare list or an envelope with an 'items' key."""
    if not path.exists():
        print(f"Error: {label} file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "items" in raw and isinstance(raw["items"], list):
        return raw["items"]
    print(
        f"Error: {label} JSON must be a list, or an object with an 'items' "
        f"list. Got: {type(raw).__name__}.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m build",
        description=(
            "Join the raw HiBid scrape with the Auction Agent's categorized "
            "JSON, validate the merged result, and write the viewer bundle."
        ),
    )
    parser.add_argument(
        "--raw",
        required=True,
        metavar="PATH",
        help="Raw scraper output (e.g. data/raw/auction_741675.json).",
    )
    parser.add_argument(
        "--categorized",
        required=True,
        metavar="PATH",
        help=(
            "Categorized JSON from the Auction Agent "
            "(e.g. data/categorized/auction_741675_categorized.json)."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output bundle path (e.g. viewer/src/data/auction_bundle.json).",
    )
    parser.add_argument(
        "--drop-orphans",
        action="store_true",
        help=(
            "If some categorized items have no matching raw lot (e.g. removed "
            "from the auction between scrapes), log each as a warning and "
            "exclude them from the bundle instead of failing. Recommended for "
            "the routine weekly build; omit it for first-time / debugging runs "
            "where you want a hard error on any mismatch."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s  %(message)s",
    )

    raw_path = Path(args.raw)
    cat_path = Path(args.categorized)
    output_path = Path(args.output)

    raw_items = _load_items(raw_path, "raw")
    categorized_items = _load_items(cat_path, "categorized")

    print(f"Loaded raw: {len(raw_items)} items from {raw_path}")
    print(f"Loaded categorized: {len(categorized_items)} items from {cat_path}")

    # Diagnostic line so the user sees what the join looks like before the
    # potentially-fatal merge call.
    from build.merge import merge, MergeError, report_overlap
    print(report_overlap(raw_items, categorized_items))

    try:
        merged = merge(
            raw_items, categorized_items, drop_orphans=args.drop_orphans
        )
    except MergeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    dropped = len(categorized_items) - len(merged)
    if args.drop_orphans and dropped:
        print(
            f"Dropped {dropped} orphan items from bundle "
            f"(categorized items with no raw match)."
        )
    print(f"Joined {len(merged)} items. Validating…")

    from build.transform import transform_all
    lots = transform_all(merged)

    # Final fidelity gates: confirm the merge actually preserved scraper fields
    n = len(lots)
    if n == 0:
        print("Error: merge produced zero items.", file=sys.stderr)
        sys.exit(1)

    titled = sum(1 for lot in lots if lot.title)
    imaged = sum(1 for lot in lots if lot.image_url)
    if titled != n:
        print(
            f"Error: only {titled}/{n} merged lots have a non-empty title. "
            "Something is wrong with the join — raw scrape may not include "
            "all categorized lots.",
            file=sys.stderr,
        )
        sys.exit(1)
    img_pct = 100.0 * imaged / n
    print(f"Fidelity: title 100% ({n}/{n}), image_url {img_pct:.1f}% ({imaged}/{n}).")
    if img_pct < 95.0:
        print(
            f"Warning: image_url coverage {img_pct:.1f}% is below the 95% gate. "
            "Bundle still written, but viewer cards will mostly show 'NO IMAGE'.",
            file=sys.stderr,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = [lot.model_dump() for lot in lots]
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(bundle, fh, ensure_ascii=False, indent=2)

    print(f"Done. Bundle written to {output_path} ({n} lots).")


if __name__ == "__main__":
    main()
