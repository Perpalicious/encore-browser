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
        "--resale",
        metavar="PATH",
        default=None,
        help=(
            "Optional resale-valuation JSON from the resale agent "
            "(e.g. data/categorized/auction_743601_resale.json). Joined onto "
            "lots by lot_number. Valuation may cover only a subset of lots — "
            "unmatched lots simply get no resale info. Omit the flag entirely "
            "to build with no resale data (the prior behaviour)."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output bundle path (e.g. viewer/src/data/auction_bundle.json).",
    )
    parser.add_argument(
        "--buckets",
        metavar="PATH",
        default=str(Path(__file__).resolve().parents[1] / "buckets.yaml"),
        help=(
            "Path to buckets.yaml (the curated Bat's List with per-bucket "
            "`group` fields). Defaults to the repo-root buckets.yaml. The "
            "build joins each lot's bat buckets to their group by name."
        ),
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

    # --- Optional resale valuation join -------------------------------------
    if args.resale:
        from build.resale import load_resale_items, build_resale_index, attach_resale

        resale_path = Path(args.resale)
        resale_items = load_resale_items(resale_path)
        resale_index = build_resale_index(resale_items)
        attached = attach_resale(merged, resale_index)
        n_merged = len(merged) or 1
        print(
            f"Resale: loaded {len(resale_items)} valuations ({len(resale_index)} "
            f"with a usable range) from {resale_path}; attached to "
            f"{attached}/{len(merged)} lots ({100.0 * attached / n_merged:.1f}%). "
            f"Lots without a valuation show no resale info."
        )

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
    categorized = sum(1 for lot in lots if lot.category_path)
    cat_pct = 100.0 * categorized / n
    print(
        f"Fidelity: title 100% ({n}/{n}), image_url {img_pct:.1f}% ({imaged}/{n}), "
        f"category_path {cat_pct:.1f}% ({categorized}/{n})."
    )
    if img_pct < 95.0:
        print(
            f"Warning: image_url coverage {img_pct:.1f}% is below the 95% gate. "
            "Bundle still written, but viewer cards will mostly show 'NO IMAGE'.",
            file=sys.stderr,
        )

    # --- Bat's List group mapping (from buckets.yaml) -----------------------
    from build.groups import load_bucket_groups, resolve_bucket_groups, UNGROUPED

    bucket_to_group, group_order = load_bucket_groups(Path(args.buckets))

    present_buckets: set[str] = set()
    for lot in lots:
        present_buckets.update(lot.bat_buckets)

    present_bucket_groups, groups_present, ungrouped = resolve_bucket_groups(
        present_buckets, bucket_to_group, group_order
    )

    if ungrouped:
        # Resilient, not fatal: evolving taxonomies will surface buckets that
        # aren't in buckets.yaml yet. Report them clearly and group as "Other".
        print(
            f"Warning: {len(ungrouped)} bat bucket(s) in the data have no group "
            f"in buckets.yaml and were placed under '{UNGROUPED}': "
            f"{', '.join(ungrouped)}. "
            "Add a `group:` for these in buckets.yaml (or re-categorize with "
            "canonical bucket names) to file them correctly.",
            file=sys.stderr,
        )
    grouped = len(present_buckets) - len(ungrouped)
    print(
        f"Bat groups: {grouped}/{len(present_buckets)} buckets mapped to a "
        f"buckets.yaml group across {len(groups_present)} group(s)."
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "lots": [lot.model_dump() for lot in lots],
        # bucket -> group for every bat bucket present in this bundle
        "bucket_groups": present_bucket_groups,
        # groups that actually contain items, in buckets.yaml order ("Other" last)
        "groups": groups_present,
    }
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(envelope, fh, ensure_ascii=False, indent=2)

    print(f"Done. Bundle written to {output_path} ({n} lots).")


if __name__ == "__main__":
    main()
