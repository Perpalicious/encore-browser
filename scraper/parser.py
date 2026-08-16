"""
Maps a single HiBid `lotSearch.results` item to the output JSON record.

The field map is:
  id                              -> id (int)
  lotNumber                       -> lot_number (str)
  lead                            -> title (str)
  description (raw)               -> description_raw (str)
  (parsed)                        -> description (str)
  (parsed)                        -> condition (str | null)
  (parsed)                        -> est_retail_price (float | null)
  featuredPicture.thumbnailLocation -> thumb_url (str)
  featuredPicture.fullSizeLocation  -> image_url (str)
  pictures[].fullSizeLocation     -> additional_images (str[])
  lotState.highBid                -> current_bid (float)
  lotState.status                 -> status (str)
  category[0].categoryName        -> hibid_category_leaf (str)
  category[0].fullCategory        -> hibid_category_path (str)
  lotState.timeLeftTitle (parsed) -> close_at (ISO 8601 str)
  (derived)                       -> lot_url (str)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .condition import parse_condition

# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------

# HiBid's timezone label is NOT trustworthy: it hardcodes "EST" year-round.
# Observed 2026-08-16 (a date squarely inside daylight time):
#     "Internet Bidding closes at: 8/16/2026 1:00:01 PM EST"
# The wall-clock number is correct Eastern local time — it matches what the
# HiBid catalog page shows — so only the label is wrong. Honouring it literally
# stamped -05:00 on summer lots and pushed every displayed closing time an hour
# off. We therefore ignore the label entirely and resolve the offset from the
# date itself in America/New_York, which applies the real DST boundaries
# (2nd Sunday in March / 1st Sunday in November) rather than approximating.
_TZ_EASTERN = ZoneInfo("America/New_York")

# Pattern: "5/24/2026 12:00:00 PM EST" or "5/24/2026 12:00:00 PM EDT"
_CLOSE_TIME_RE = re.compile(
    r"(?P<dt>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM))\s+(?P<tz>E[SD]T)",
    re.IGNORECASE,
)

_DT_FORMAT = "%m/%d/%Y %I:%M:%S %p"


def _parse_close_at(time_left_title: Optional[str]) -> Optional[str]:
    """
    Parse a timeLeftTitle like "5/24/2026 12:00:00 PM EST" into an ISO 8601
    string with explicit UTC offset.

    The trailing zone label is matched only so the timestamp can be located in
    the sentence; its value is deliberately discarded (see _TZ_EASTERN above —
    HiBid says "EST" in August). The wall-clock number is Eastern local time.

    Returns None if the input is missing or unparseable.
    """
    if not time_left_title:
        return None
    m = _CLOSE_TIME_RE.search(time_left_title)
    if not m:
        return None
    dt_str = m.group("dt").strip()
    try:
        naive_dt = datetime.strptime(dt_str, _DT_FORMAT)
    except ValueError:
        return None

    aware_dt = naive_dt.replace(tzinfo=_TZ_EASTERN)
    return aware_dt.isoformat()


# ---------------------------------------------------------------------------
# Main mapping function
# ---------------------------------------------------------------------------

LOT_URL_TEMPLATE = "https://encoreauctions.hibid.com/lot/{id}/?ref=catalog"


def map_lot(item: dict[str, Any]) -> dict[str, Any]:
    """
    Map a single lotSearch result item to the output record shape.

    Missing optional fields are treated as null / empty gracefully.
    """
    lot_id = item.get("id")
    lot_number = item.get("lotNumber") or ""
    title = item.get("lead") or ""
    description_raw = item.get("description") or ""

    # Parse description
    condition, est_retail_price, description_clean = parse_condition(description_raw)

    # Featured picture
    featured = item.get("featuredPicture") or {}
    thumb_url = featured.get("thumbnailLocation") or ""
    image_url = featured.get("fullSizeLocation") or ""

    # Additional pictures (exclude featured to avoid duplication)
    pictures_raw = item.get("pictures") or []
    additional_images = [
        p.get("fullSizeLocation", "")
        for p in pictures_raw
        if p.get("fullSizeLocation") and p.get("fullSizeLocation") != image_url
    ]

    # Lot state
    lot_state = item.get("lotState") or {}
    current_bid = lot_state.get("highBid")
    if current_bid is not None:
        try:
            current_bid = float(current_bid)
        except (ValueError, TypeError):
            current_bid = None
    status = lot_state.get("status") or ""
    time_left_title = lot_state.get("timeLeftTitle")
    close_at = _parse_close_at(time_left_title)

    # Category — HiBid returns an array ordered leaf → root, e.g.
    #   [{categoryName: "Bed / Bath Items", fullCategory: "Home Goods & Decor - Home Goods - Bed / Bath Items"},
    #    {categoryName: "Home Goods", ...},
    #    {categoryName: "Home Goods & Decor", ...}]
    # We preserve the FULL ordered path (root → leaf) so the viewer can build a
    # hierarchical filter. Each element of `category_path` is a discrete
    # category name (no delimiter ambiguity), reversed from the leaf-first array.
    category_raw = item.get("category")
    category_list: list[dict] = []
    if isinstance(category_raw, list):
        category_list = category_raw
    elif isinstance(category_raw, dict):
        category_list = [category_raw]

    # root → leaf
    category_path = [
        (c or {}).get("categoryName") or ""
        for c in reversed(category_list)
    ]
    category_path = [name for name in category_path if name]

    # Compat fields: leaf name + full breadcrumb string from the leaf entry.
    hibid_category_leaf = category_path[-1] if category_path else ""
    hibid_category_path = ""
    if category_list:
        leaf_entry = category_list[0] or {}
        hibid_category_path = leaf_entry.get("fullCategory") or ""

    # Derived lot URL
    lot_url = LOT_URL_TEMPLATE.format(id=lot_id) if lot_id is not None else ""

    return {
        "id": lot_id,
        "lot_number": lot_number,
        "title": title,
        "description_raw": description_raw,
        "description": description_clean,
        "condition": condition,
        "est_retail_price": est_retail_price,
        "thumb_url": thumb_url,
        "image_url": image_url,
        "additional_images": additional_images,
        "current_bid": current_bid,
        "status": status,
        "category_path": category_path,
        "hibid_category_leaf": hibid_category_leaf,
        "hibid_category_path": hibid_category_path,
        "close_at": close_at,
        "lot_url": lot_url,
    }
