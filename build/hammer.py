"""
Join past auctions' hammer prices onto this week's lots.

`tools/hammer.py` writes one file per closed auction under data/hammer/, each
holding one row per PRODUCT (title + condition) with what that product actually
sold for. This module indexes every such file and marks each lot in this week's
build with the product it matches, so the viewer can show "sold 6× last week,
median $14" on a lot that is about to run again.

Mirrors build/resale.py exactly, including the leniency: the flag is optional,
a lot with no match keeps `hammer_key = None`, and the build never fails on
missing hammer data. Roughly one lot in three matches (22.8% against the
previous week alone, 36.9% against five archived weeks, measured on the
2026-09-13 auction).

Why the history does not live on the lot
----------------------------------------
58 lots routinely share one product, so copying a product's week-by-week
history onto every lot would multiply the same rows dozens of times over in a
bundle the browser has to parse. Instead each lot carries a `hammer_key`
pointing into a top-level `hammer` map, deduped by product. Only keys some lot
actually references are emitted.

Join key
--------
``"TITLE|CONDITION"``, upper-cased — the same (title, condition) pair
`tools/slim_resale.py:group_key` groups on, rebuilt here from the merged lot's
own fields (which `scraper/parser.py` produced with the same parser the hammer
pull used). Neither `lot_number` nor HiBid's `id` can be used: both are
per-listing and recycle week to week.

Two known, accepted collisions: two different products sharing a 50-char
truncated `lead` (1.1% of lots are cut at exactly 50 chars), and a title
containing a literal "|". Condition-in-key absorbs most of the first, and this
is a display line, not a valuation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Weeks kept per product. Beyond about two months a price is a different
# market, and the detail table stops being readable.
MAX_WEEKS = 8

# What a week's row carries into the bundle. `prices` is deliberately absent:
# the per-lot finals are only needed to re-aggregate, which happens in
# tools/hammer.py against the file on disk, never in the browser.
_WEEK_FIELDS = ("close_date", "sold", "unsold", "median", "low", "high")


def hammer_key(title: Any, condition: Any) -> str:
    """The bundle's compact product key: ``"TITLE|CONDITION"``, upper-cased."""
    t = str(title or "").strip()
    c = str(condition or "").strip()
    return f"{t}|{c}".upper()


def _to_number(value: Any) -> float | None:
    """Coerce a price-like value to a float, or None if absent/unparseable."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_count(value: Any) -> int:
    """Coerce a count to a non-negative int; anything unparseable is 0."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, n)


def load_hammer_files(directory: Path) -> list[dict[str, Any]]:
    """
    Load every ``*.json`` in ``directory``, newest close_date first.

    A file that fails to parse, or that is not a hammer file at all, is
    SKIPPED with a warning rather than failing the build — the directory is
    append-only history that nothing else validates, and one bad file must not
    cost the whole week's build.
    """
    if not directory.is_dir():
        logger.warning(
            "Hammer directory not found: %s. Building with no hammer history.",
            directory,
        )
        return []

    files: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable hammer file %s: %s", path, exc)
            continue
        if not isinstance(raw, dict) or not isinstance(raw.get("products"), list):
            logger.warning(
                "Skipping hammer file %s: expected an object with a 'products' "
                "list.",
                path,
            )
            continue
        files.append(raw)

    # Descending close_date, so index 0 of every product's history is the most
    # recent week. Recency wins on the card; the detail shows all of it.
    files.sort(key=lambda f: str(f.get("close_date") or ""), reverse=True)
    return files


def build_hammer_index(files: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """
    Map product key -> that product's weeks, most recent first, capped at
    MAX_WEEKS.

    ``files`` must already be sorted newest-first (``load_hammer_files`` does
    it), since the per-product order is simply the order the files arrive in.
    """
    index: dict[str, list[dict[str, Any]]] = {}
    for f in files:
        close_date = str(f.get("close_date") or "")
        for product in f.get("products") or []:
            if not isinstance(product, dict):
                continue
            key = hammer_key(product.get("title"), product.get("condition"))
            if key == "|":
                continue  # no title and no condition — nothing to join on
            weeks = index.setdefault(key, [])
            if len(weeks) >= MAX_WEEKS:
                continue
            weeks.append(
                {
                    "close_date": close_date,
                    "sold": _to_count(product.get("sold")),
                    "unsold": _to_count(product.get("unsold")),
                    "median": _to_number(product.get("median")),
                    "low": _to_number(product.get("low")),
                    "high": _to_number(product.get("high")),
                }
            )
    return index


def attach_hammer(
    merged_items: list[dict[str, Any]],
    index: dict[str, list[dict[str, Any]]],
) -> int:
    """
    Mutate ``merged_items`` in place, stamping ``hammer_key`` on every lot whose
    (title, condition) matches a product in ``index``.

    Returns the number of lots that matched. Unmatched lots are left untouched,
    so their `hammer_key` stays at the schema default (None) and the viewer
    renders no history line.
    """
    attached = 0
    for item in merged_items:
        key = hammer_key(item.get("title"), item.get("condition"))
        if key in index:
            item["hammer_key"] = key
            attached += 1
    return attached


def used_index(
    merged_items: list[dict[str, Any]],
    index: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """
    The subset of ``index`` some lot actually references, in the bundle's shape.

    Shipping the whole index would carry every product of every archived week,
    most of which are not in this auction at all.
    """
    used = {
        str(item["hammer_key"])
        for item in merged_items
        if item.get("hammer_key")
    }
    return {key: {"weeks": index[key]} for key in sorted(used) if key in index}


def describe(
    files: list[dict[str, Any]],
    index: dict[str, list[dict[str, Any]]],
    attached: int,
    total: int,
) -> str:
    """The one-line report the build prints, in the style of the resale line."""
    pct = 100.0 * attached / total if total else 0.0
    return (
        f"Hammer: {len(index)} products across {len(files)} week(s); "
        f"{attached}/{total} lots matched ({pct:.1f}%). "
        f"Lots without a match show no sale history."
    )
