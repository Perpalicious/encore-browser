"""
CLI entry point.

Usage:
    python -m scraper --auction-id 741675 --output data/raw/auction_741675.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .client import fetch_all_lots
from .parser import map_lot


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    _configure_logging()

    parser = argparse.ArgumentParser(
        prog="python -m scraper",
        description="Scrape all lots for a HiBid auction and write a JSON file.",
    )
    parser.add_argument(
        "--auction-id",
        type=int,
        required=True,
        metavar="INT",
        help="Numeric HiBid auction ID (e.g. 741675)",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output JSON file path (e.g. data/raw/auction_741675.json)",
    )
    args = parser.parse_args(argv)

    auction_id: int = args.auction_id
    output_path = Path(args.output)

    logging.getLogger(__name__).info(
        "Scraping auction %d → %s", auction_id, output_path
    )

    try:
        auction_name, raw_items = fetch_all_lots(auction_id)
    except RuntimeError as exc:
        logging.getLogger(__name__).error("Scrape failed: %s", exc)
        return 1

    items = [map_lot(item) for item in raw_items]

    output = {
        "auction_id": auction_id,
        "auction_name": auction_name,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(items),
        "items": items,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    logging.getLogger(__name__).info(
        "Wrote %d items to %s", len(items), output_path
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
