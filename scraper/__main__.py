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


def load_prior_first_seen(path: Path) -> dict[str, str]:
    """
    ``{id: first_seen}`` for every item already in ``path``, so a re-scrape
    keeps the timestamp of the run that first saw each lot.

    Keyed on HiBid's item ``id``, never ``lot_number`` — on two-auction weeks
    the raw file's lot_numbers are rewritten to ``S-``/``M-`` in place before
    combining, and the next scrape must still recognise those items. An item
    written before this field existed inherits its file's ``scraped_at``.
    Anything unreadable (missing file, bare list, malformed JSON) is simply
    treated as a first scrape.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            prior = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(prior, dict):
        return {}
    fallback = prior.get("scraped_at")
    out: dict[str, str] = {}
    for item in prior.get("items") or []:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        first_seen = item.get("first_seen") or fallback
        if first_seen:
            out[str(item["id"])] = str(first_seen)
    return out


def stamp_first_seen(
    items: list[dict], prior: dict[str, str], scraped_at: str
) -> int:
    """Set ``first_seen`` on every item; returns how many are new this run."""
    new = 0
    for item in items:
        carried = prior.get(str(item.get("id")))
        if carried is None:
            new += 1
        item["first_seen"] = carried or scraped_at
    return new


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

    scraped_at = datetime.now(timezone.utc).isoformat()
    prior = load_prior_first_seen(output_path)
    n_new = stamp_first_seen(items, prior, scraped_at)
    if prior:
        logging.getLogger(__name__).info(
            "Re-scrape: %d of %d lots are new since %s",
            n_new, len(items), output_path,
        )

    output = {
        "auction_id": auction_id,
        "auction_name": auction_name,
        "scraped_at": scraped_at,
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
