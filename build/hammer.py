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

Other conditions of the same title
----------------------------------
A `Good` lot whose title only ever ran as `Excellent` gets no exact match, but
the `Excellent` history is still worth seeing — labelled as such. Each lot
therefore also carries `hammer_alt_keys`: the keys of every OTHER condition of
the same title that has history, nearest grade first on `CONDITION_LADDER`.
Measured on 2026-09-16 against twelve archived weeks this lifts the share of
lots with something to show from 41.2% to 55.3%. The viewer never blends the
two: the exact key is the lot's own history, the alternates are shown under
their own grade, and a lot with neither shows nothing.
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

# HiBid's main grades, best to worst, upper-cased to match the key. Spelled as
# `scraper/condition.py:CONDITION_LABELS` spells them, but NOT in that order —
# that list interleaves "Best Before (Grocery)" and "New With Defects" for the
# filter chips, and neither sits on a price ladder. Used only to order a lot's
# `hammer_alt_keys` so the nearest grade comes first; a grade not listed here
# sorts after every listed one.
CONDITION_LADDER = (
    "BRAND NEW - SEALED",
    "BRAND NEW - OPEN BOX",
    "NEW (ADJUSTED QUANTITY)",
    "EXCELLENT",
    "GOOD",
    "NEW WITH DEFECTS",
    "FAIR",
    "HEAVILY USED",
    "FOR PARTS ONLY",
)
_LADDER_RANK = {c: i for i, c in enumerate(CONDITION_LADDER)}


def hammer_key(title: Any, condition: Any) -> str:
    """The bundle's compact product key: ``"TITLE|CONDITION"``, upper-cased."""
    t = str(title or "").strip()
    c = str(condition or "").strip()
    return f"{t}|{c}".upper()


def split_key(key: str) -> tuple[str, str]:
    """``"TITLE|CONDITION"`` -> ``(TITLE, CONDITION)``, splitting on the LAST bar."""
    title, _, condition = key.rpartition("|")
    return title, condition


def alt_key_order(own_condition: str, candidate: str) -> tuple[int, int, str]:
    """
    Sort key placing the grade nearest ``own_condition`` first.

    Ties go to the WORSE grade (a `Good` lot borrows from `Fair` before
    `Excellent`), so a borrowed figure errs low rather than high. Grades not on
    the ladder sort last, alphabetically; a lot with no parseable condition
    sees the ladder best-first.
    """
    own = _LADDER_RANK.get(own_condition)
    rank = _LADDER_RANK.get(candidate)
    if rank is None:
        return (2, 0, candidate)
    if own is None:
        return (1, rank, candidate)
    return (0, abs(rank - own) * 2 + (0 if rank > own else 1), candidate)


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
    # Siblings a lot may borrow from. A product whose condition failed to parse
    # in some past week keys as "TITLE|"; it still matches a lot in the same
    # state exactly, but "No grade: sold 2×" is not a useful stand-in, so it is
    # never offered as an alternate.
    by_title: dict[str, list[str]] = {}
    for key in index:
        title, condition = split_key(key)
        if condition:
            by_title.setdefault(title, []).append(key)

    attached = 0
    for item in merged_items:
        key = hammer_key(item.get("title"), item.get("condition"))
        title, condition = split_key(key)
        if key in index:
            item["hammer_key"] = key
            attached += 1
        siblings = [k for k in by_title.get(title, ()) if k != key]
        if siblings:
            siblings.sort(key=lambda k: alt_key_order(condition, split_key(k)[1]))
            item["hammer_alt_keys"] = siblings
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
    used: set[str] = set()
    for item in merged_items:
        if item.get("hammer_key"):
            used.add(str(item["hammer_key"]))
        used.update(str(k) for k in item.get("hammer_alt_keys") or ())
    return {key: {"weeks": index[key]} for key in sorted(used) if key in index}


def count_alt_only(merged_items: list[dict[str, Any]]) -> int:
    """Lots with no exact match but at least one other-condition history."""
    return sum(
        1
        for item in merged_items
        if not item.get("hammer_key") and item.get("hammer_alt_keys")
    )


def describe(
    files: list[dict[str, Any]],
    index: dict[str, list[dict[str, Any]]],
    attached: int,
    total: int,
    alt_only: int = 0,
) -> str:
    """The one-line report the build prints, in the style of the resale line."""
    pct = 100.0 * attached / total if total else 0.0
    alt_pct = 100.0 * alt_only / total if total else 0.0
    return (
        f"Hammer: {len(index)} products across {len(files)} week(s); "
        f"{attached}/{total} lots matched ({pct:.1f}%), "
        f"{alt_only} more ({alt_pct:.1f}%) only via another condition. "
        f"Lots with neither show no sale history."
    )
