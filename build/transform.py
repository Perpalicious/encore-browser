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


def _normalise_subtype(value: object) -> str | None:
    """
    Normalise the flagging pass's free-form `bats_subtype`.

    The pass is asked for 1-3 lowercase words and to reuse wording across the
    run, but it is free text, so "Scrub Brushes", "scrub  brushes" and
    "scrub brushes " must collapse to one node in the drill-down rather than
    three. Anything empty becomes None so the viewer can treat "no subtype" as
    a single condition.
    """
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).lower()
    return cleaned or None


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


def _to_price(value: Any) -> float | None:
    """Coerce a price-like value to a float, or None if absent/unparseable."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resale_passthrough(item: dict[str, Any]) -> dict[str, Any]:
    """
    Carry the estimated-retail and (optional) resale-valuation fields onto the
    Lot shape. All resale fields are absent for lots the valuation pass did not
    cover; they default to None and the viewer simply shows no resale info.

    Enum values (resale_confidence/resale_outlook) are passed through as-is —
    the resale join (build/resale.py) already normalises or nulls them, and the
    Lot schema validates the allowed set, so a bad value fails loudly.
    """
    return {
        "est_retail_price": _to_price(item.get("est_retail_price")),
        "est_resale_low": _to_price(item.get("est_resale_low")),
        "est_resale_high": _to_price(item.get("est_resale_high")),
        "resale_confidence": item.get("resale_confidence") or None,
        "resale_outlook": item.get("resale_outlook") or None,
        "resale_reasoning": item.get("resale_reasoning") or None,
    }


def _personal_passthrough(item: dict[str, Any]) -> dict[str, Any]:
    """
    Carry the optional personal-match fields onto the Lot shape. Categorized
    files produced before the personal-match pass lack these fields entirely;
    they default to None and the lot simply omits personal-match info — same
    tolerant pattern as the resale fields above.
    """
    tags = item.get("personal_tags")
    types = item.get("match_types")
    return {
        "personal_match": item.get("personal_match"),
        "personal_tags": [str(t) for t in tags] if isinstance(tags, list) else None,
        "match_strength": item.get("match_strength") or None,
        "match_types": [str(t) for t in types] if isinstance(types, list) else None,
        "personal_reasoning": item.get("personal_reasoning") or None,
    }


def _resolve_categories(
    item: dict[str, Any], fallback_subcategory: str
) -> tuple[list[str], str, str]:
    """
    Determine (category_path, category, subcategory) for a lot.

    HiBid's native category tree is the source of truth. In the real build
    flow the merge step copies the raw scrape's ``category_path`` (root → leaf)
    onto the item, so we use it directly: ``category`` is the root, and
    ``subcategory`` is the leaf.

    For standalone categorized inputs that lack ``category_path`` (e.g. unit
    test fixtures, or a categorized file processed without a raw join), we fall
    back to the flat ``category`` field plus a caller-supplied subcategory, and
    synthesise a best-effort path from them.
    """
    raw_path = item.get("category_path")
    if isinstance(raw_path, list) and any(raw_path):
        path = [str(c) for c in raw_path if c]
        return path, path[0], path[-1]

    # Fallback: no native path available.
    category = item.get("category") or ""
    subcategory = fallback_subcategory or ""
    path = _dedup_ordered([category, subcategory])
    return path, category, subcategory


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

    # Categories come from HiBid's native tree (via the raw scrape's
    # category_path), NOT from the agent. Fallback to bats_subcategory only
    # when no native path is present (standalone categorized input).
    # Nice Picks were removed; any nice_pick_* fields in the input are ignored.
    category_path, category, subcategory = _resolve_categories(
        item, fallback_subcategory=bats_sub
    )

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
        "category": category,
        "subcategory": subcategory,
        "category_path": category_path,
        "is_bat": bool(item.get("is_bats_list", False)),
        "bat_buckets": bat_buckets,
        "bat_subtype": _normalise_subtype(item.get("bats_subtype")),
        # Kept, not just used to derive `day`: the viewer shows the closing
        # time per lot and marks a lot ENDED once it passes.
        "close_at": item.get("close_at") or None,
        "confidence": _bucket_confidence(item.get("predicted_confidence")),
        **_resale_passthrough(item),
        **_personal_passthrough(item),
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

    category_path, category, subcategory = _resolve_categories(
        item, fallback_subcategory=item.get("subcategory") or ""
    )

    return {
        "day": day or "",
        "lot_number": str(item.get("lot_number", "")),
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "condition": item.get("condition") or None,
        "thumb_url": item.get("thumb_url") or "",
        "image_url": item.get("image_url") or "",
        "lot_url": item.get("lot_url") or "",
        "category": category,
        "subcategory": subcategory,
        "category_path": category_path,
        "is_bat": bool(item.get("is_bats_list", False)),
        "bat_buckets": bat_buckets,
        "bat_subtype": _normalise_subtype(item.get("bats_subtype")),
        "close_at": item.get("close_at") or None,
        "confidence": confidence,
        **_resale_passthrough(item),
        **_personal_passthrough(item),
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
