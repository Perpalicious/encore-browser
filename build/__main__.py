"""CLI entry point: python -m build --input PATH --output PATH"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transform a categorized auction JSON into a flat Lot[] bundle."
    )
    parser.add_argument("--input", required=True, help="Path to categorized JSON file")
    parser.add_argument("--output", required=True, help="Path for the output bundle JSON")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {input_path}…")
    with input_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    # Accept either a bare list or an envelope {items: [...]}
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and "items" in raw:
        items = raw["items"]
    else:
        print(
            "Error: input JSON must be a list of items or an object with an 'items' key.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Transforming {len(items)} items…")

    # Import here so import errors surface clearly
    from build.transform import transform_all

    lots = transform_all(items)

    print(f"Validated {len(lots)} lots. Writing bundle…")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = [lot.model_dump() for lot in lots]

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(bundle, fh, ensure_ascii=False, indent=2)

    print(f"Done. Bundle written to {output_path} ({len(bundle)} lots).")


if __name__ == "__main__":
    main()
