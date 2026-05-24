"""
Join a raw scrape with a categorized JSON (the Auction Agent's enrichment-only
output) into merged items the transform layer can validate.

Why this exists
---------------
The Auction Agent (external, in ChatGPT) emits only enrichment fields:
``category``, ``subcategory``, ``confidence``, ``is_bats_list``,
``bats_buckets`` / ``bats_category`` / ``bats_subcategory``, ``is_nice_pick``,
``nice_pick_reason`` (or ``nice_pick_*`` variants), plus the original
``lot_number`` (which in practice has been the HiBid numeric ``id``). It
drops the scraper-provided fields the viewer needs to actually render
anything: title, image_url, thumb_url, lot_url, description, condition,
close_at, day.

We therefore must re-join the categorized output back to the raw scrape on
the lot key. Every categorized item must find its raw counterpart — a
silent miss would produce empty-field cards.

Join key
--------
The Auction Agent's ``lot_number`` field has, in observed samples, contained
the HiBid numeric ``id`` (e.g. ``"282846987"``), not the display lot number
(``"1"``, ``"7586a"``). To be robust to either convention we try both:

    1. raw["id"] (as string) == categorized["lot_number"]
    2. raw["lot_number"] == categorized["lot_number"]

If a categorized item finds no raw match by either key, we raise — never
silently drop.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


class MergeError(RuntimeError):
    """Raised when the join cannot complete (unmatched items)."""


def _build_raw_index(raw_items: list[dict[str, Any]]) -> tuple[dict[str, dict], dict[str, dict]]:
    """
    Return two indexes for fast lookup:
        by_id[str(id)]            -> raw item
        by_lot_number[lot_number] -> raw item
    """
    by_id: dict[str, dict] = {}
    by_lot_number: dict[str, dict] = {}
    for item in raw_items:
        raw_id = item.get("id")
        if raw_id is not None:
            by_id[str(raw_id)] = item
        lot_num = item.get("lot_number")
        if lot_num is not None and lot_num != "":
            # Last write wins for collisions (the raw scrape should not have
            # duplicate display lot numbers, but if it does we keep the latest).
            by_lot_number[str(lot_num)] = item
    return by_id, by_lot_number


def _merge_one(raw: dict[str, Any], cat: dict[str, Any]) -> dict[str, Any]:
    """
    Combine one raw scrape item with one categorized item. Raw fields always
    win for everything the scraper provides; the categorized item contributes
    only enrichment.

    The merged dict is the input expected by transform.transform_item — i.e.
    Shape A or Shape B as the transformer already understands them — but with
    every raw field (title, image_url, etc.) present.
    """
    merged: dict[str, Any] = {}

    # --- Scraper-provided fields (authoritative from raw) -------------------
    merged["lot_number"] = str(raw.get("lot_number", ""))
    merged["title"] = raw.get("title", "") or ""
    # Use the scraper's cleaned `description` (structured lines stripped).
    # NOT description_raw — that includes "Condition:" / "Est. Retail Price:"
    # noise that would clobber the cleaner agent-supplied description.
    merged["description"] = raw.get("description") or ""
    merged["thumb_url"] = raw.get("thumb_url", "") or ""
    merged["image_url"] = raw.get("image_url", "") or ""
    merged["lot_url"] = raw.get("lot_url", "") or ""
    merged["condition"] = raw.get("condition")  # may be None
    merged["close_at"] = raw.get("close_at")
    # `current_bid` and `status` aren't on the Lot shape, but pass through
    merged["current_bid"] = raw.get("current_bid")
    merged["status"] = raw.get("status")

    # --- Enrichment-provided fields (authoritative from categorized) --------
    # Pass through every categorized field so the existing shape detection
    # (Shape A vs Shape B) in transform.py continues to work without changes.
    # For scraper-authoritative fields, raw wins whenever raw has a value;
    # the agent only fills in if raw is empty.
    _SCRAPER_AUTHORITATIVE = {
        "title", "description", "thumb_url", "image_url",
        "lot_url", "url", "condition", "close_at",
    }
    for key, value in cat.items():
        if key in _SCRAPER_AUTHORITATIVE:
            if merged.get(key):
                # Raw already has a value; never let agent overwrite.
                continue
            if not value:
                # Both empty: leave the empty raw value.
                continue
        merged[key] = value

    # Preserve the lot_number key so transform can stringify it
    merged["lot_number"] = str(raw.get("lot_number", "")) or str(cat.get("lot_number", ""))

    # Derive `day` from close_at if neither source supplied it
    if "day" not in merged or not merged.get("day"):
        from .transform import _derive_day_from_close_at
        merged["day"] = _derive_day_from_close_at(merged.get("close_at")) or ""

    return merged


def merge(
    raw_items: list[dict[str, Any]],
    categorized_items: list[dict[str, Any]],
    *,
    drop_orphans: bool = False,
) -> list[dict[str, Any]]:
    """
    Join categorized items to their raw counterparts.

    Default behaviour: raise ``MergeError`` if any categorized item is
    unmatched (e.g. a lot was removed from the auction between scrapes).

    With ``drop_orphans=True``: log each orphan via ``logging.warning`` with
    its lot_number and any available enrichment fields (category / subcategory
    / bats_*), exclude it from the result, and continue. Useful as the
    routine weekly setting where occasional dropped lots are expected.
    """
    by_id, by_lot_number = _build_raw_index(raw_items)
    merged: list[dict[str, Any]] = []
    unmatched: list[tuple[int, str, dict[str, Any]]] = []

    for idx, cat in enumerate(categorized_items):
        key = str(cat.get("lot_number") or "")
        raw = by_id.get(key) or by_lot_number.get(key)
        if raw is None:
            unmatched.append((idx, key, cat))
            continue
        merged.append(_merge_one(raw, cat))

    if not unmatched:
        return merged

    if drop_orphans:
        for idx, key, cat in unmatched:
            enrichment = {
                k: cat.get(k)
                for k in (
                    "category",
                    "subcategory",
                    "bats_category",
                    "bats_subcategory",
                    "is_bats_list",
                    "is_nice_pick",
                )
                if cat.get(k)
            }
            logger.warning(
                "Dropping orphan categorized item #%d (lot_number=%r): %s",
                idx,
                key,
                enrichment or "no enrichment fields",
            )
        logger.warning(
            "Dropped %d orphan items from bundle "
            "(categorized items with no raw match)",
            len(unmatched),
        )
        return merged

    examples = ", ".join(f"#{i}={k!r}" for i, k, _ in unmatched[:5])
    suffix = "" if len(unmatched) <= 5 else f" (+{len(unmatched) - 5} more)"
    raise MergeError(
        f"Join failed: {len(unmatched)} of {len(categorized_items)} categorized "
        f"items could not be matched to any raw item by id or lot_number. "
        f"Examples: {examples}{suffix}. Re-run the scraper for this auction "
        f"and re-upload to the Auction Agent so the two files describe the "
        f"same lots — or pass --drop-orphans to skip them and continue."
    )


def report_overlap(
    raw_items: list[dict[str, Any]], categorized_items: list[dict[str, Any]]
) -> str:
    """
    Diagnostic string describing how the two files line up. Useful in CLI
    output. Does not raise — just describes.
    """
    n_raw = len(raw_items)
    n_cat = len(categorized_items)
    by_id, by_lot_number = _build_raw_index(raw_items)
    matched_id = 0
    matched_ln = 0
    unmatched = 0
    for cat in categorized_items:
        key = str(cat.get("lot_number") or "")
        if key in by_id:
            matched_id += 1
        elif key in by_lot_number:
            matched_ln += 1
        else:
            unmatched += 1
    return (
        f"raw items: {n_raw}; categorized items: {n_cat}; "
        f"matched by raw.id: {matched_id}; matched by raw.lot_number: {matched_ln}; "
        f"unmatched: {unmatched}"
    )
