"""Transform categorized auction JSON (Shape A or Shape B) into a flat Lot[] bundle."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .schema import Lot

# Lot URL pattern for validation
_LOT_URL_RE = re.compile(r"^https://encoreauctions\.hibid\.com/lot/")


def _is_shape_b(item: dict[str, Any]) -> bool:
    """Detect Shape B (real agent output) by presence of 'bats_category' field."""
    return "bats_category" in item


def _bucket_confidence(value: float | None) -> str:
    """Convert a float confidence score to a low/medium/high bucket."""
    if value is None:
        return "low"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "low"
    if v < 0.34:
        return "low"
    if v < 0.67:
        return "medium"
    return "high"


def _derive_day_from_close_at(close_at: str | None) -> str:
    """Derive weekday name from an ISO-8601 close_at string."""
    if not close_at:
        return ""
    try:
        dt = datetime.fromisoformat(close_at.replace("Z", "+00:00"))
        return dt.strftime("%A")
    except ValueError:
        return ""


def _dedup_ordered(values: list[str]) -> list[str]:
    """Remove duplicates while preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            result.append(v)
    return result


def _transform_shape_b(item: dict[str, Any]) -> dict[str, Any]:
    """Normalise a Shape B item (real agent output) to the Lot shape."""
    # lot_url: prefer `url` field if it looks like a lot URL, else fall back to lot_url
    url_field = item.get("url", "")
    lot_url_field = item.get("lot_url", "")
    if url_field and _LOT_URL_RE.match(url_field):
        lot_url = url_field
    elif lot_url_field:
        lot_url = lot_url_field
    else:
        lot_url = url_field or lot_url_field

    # bat_buckets: non-empty values from [bats_category, bats_subcategory], deduped
    bats_cat = item.get("bats_category", "") or ""
    bats_sub = item.get("bats_subcategory", "") or ""
    bat_buckets = _dedup_ordered([bats_cat, bats_sub])

    # subcategory: prefer bats_subcategory, then nice_pick_subcategory
    subcategory = bats_sub or (item.get("nice_pick_subcategory") or "")

    # nice_pick_reason: prefer nice_pick_subcategory, then nice_pick_category
    nice_pick_reason = (item.get("nice_pick_subcategory") or "") or (item.get("nice_pick_category") or "")

    # day: from input field; derive from close_at if missing
    day = item.get("day") or _derive_day_from_close_at(item.get("close_at"))

    return {
        "day": day or "",
        "lot_number": str(item.get("lot_number", "")),
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "condition": item.get("condition") or None,
        "thumb_url": item.get("thumb_url") or "",
        "image_url": item.get("image_url") or "",
        "lot_url": lot_url,
        "category": item.get("category") or "",
        "subcategory": subcategory,
        "is_bat": bool(item.get("is_bats_list", False)),
        "bat_buckets": bat_buckets,
        "is_nice_pick": bool(item.get("is_nice_pick", False)),
        "nice_pick_reason": nice_pick_reason,
        "confidence": _bucket_confidence(item.get("predicted_confidence")),
    }


def _transform_shape_a(item: dict[str, Any]) -> dict[str, Any]:
    """Normalise a Shape A item (brief's idealized schema) to the Lot shape."""
    # day: from input field or derive from close_at
    day = item.get("day") or _derive_day_from_close_at(item.get("close_at"))

    # confidence: already a string in Shape A, but bucket just in case it's a float
    raw_conf = item.get("confidence", "low")
    if isinstance(raw_conf, (int, float)):
        confidence = _bucket_confidence(raw_conf)
    elif raw_conf in ("low", "medium", "high"):
        confidence = raw_conf
    else:
        confidence = "low"

    # bats_buckets → bat_buckets
    bats_buckets_raw = item.get("bats_buckets") or []
    bat_buckets = _dedup_ordered([str(b) for b in bats_buckets_raw])

    return {
        "day": day or "",
        "lot_number": str(item.get("lot_number", "")),
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "condition": item.get("condition") or None,
        "thumb_url": item.get("thumb_url") or "",
        "image_url": item.get("image_url") or "",
        "lot_url": item.get("lot_url") or "",
        "category": item.get("category") or "",
        "subcategory": item.get("subcategory") or "",
        "is_bat": bool(item.get("is_bats_list", False)),
        "bat_buckets": bat_buckets,
        "is_nice_pick": bool(item.get("is_nice_pick", False)),
        "nice_pick_reason": item.get("nice_pick_reason") or "",
        "confidence": confidence,
    }


def transform_item(item: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the appropriate normaliser based on detected input shape."""
    if _is_shape_b(item):
        return _transform_shape_b(item)
    return _transform_shape_a(item)


def transform_all(items: list[dict[str, Any]]) -> list[Lot]:
    """Transform and validate every item, returning a list of Lot objects.

    Raises SystemExit with a descriptive message on the first validation failure.
    Does NOT write partial output.
    """
    import sys
    from pydantic import ValidationError

    lots: list[Lot] = []
    for idx, item in enumerate(items):
        raw = transform_item(item)
        try:
            lot = Lot(**raw)
        except ValidationError as exc:
            lot_num = item.get("lot_number", "<unknown>")
            errors = exc.errors()
            for err in errors:
                field = ".".join(str(loc) for loc in err["loc"])
                value = err.get("input")
                print(
                    f"Validation error at item index {idx} (lot_number={lot_num!r}): "
                    f"field={field!r}, value={value!r} ({type(value).__name__}): "
                    f"{err['msg']}",
                    file=sys.stderr,
                )
            sys.exit(1)
        lots.append(lot)
    return lots
