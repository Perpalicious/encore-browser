"""
Join an optional resale-valuation file onto the merged lots.

The resale valuation is produced by a separate external agent pass (analogous
to the categorization agent). It emits, per lot it chose to value:

    {
      "lot_number": "1a",
      "est_resale_low": 40,
      "est_resale_high": 70,
      "resale_confidence": "medium",   # high | medium | low
      "resale_outlook": "good",        # good | fair | poor
      "reasoning": "Comparable units sell for ..."
    }

Valuation typically covers only a SUBSET of lots, so the join is lenient: a
lot with no resale entry simply keeps its resale fields as None, and the build
never fails on missing resale data. The file is optional entirely — when
``--resale`` is not passed, no resale fields are attached.

Join key
--------
The resale file keys on ``lot_number`` (the display lot number, e.g. "1a"),
matching the merged lots' ``lot_number``. We also accept the HiBid numeric id
as a fallback, mirroring merge.py, in case a resale file keys on id instead.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIDENCE = {"low", "medium", "high"}
_OUTLOOK = {"good", "fair", "poor"}


def _to_price(value: Any) -> float | None:
    """Coerce a price-like value to a float, or None if absent/unparseable."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_enum(value: Any, allowed: set[str]) -> str | None:
    """Lowercase/strip an enum-ish value; return None if not in ``allowed``."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    return v if v in allowed else None


def load_resale_items(path: Path) -> list[dict[str, Any]]:
    """Load a resale file (a bare list, or an envelope with an 'items' list)."""
    if not path.exists():
        print(f"Error: resale file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        return raw["items"]
    print(
        f"Error: resale JSON must be a list, or an object with an 'items' "
        f"list. Got: {type(raw).__name__}.",
        file=sys.stderr,
    )
    sys.exit(1)


def build_resale_index(resale_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Map lot_number (as a stripped string) -> normalised resale fields.

    Each value contains exactly the five resale keys the merged item expects:
    est_resale_low, est_resale_high, resale_confidence, resale_outlook,
    resale_reasoning. Entries with no usable low/high range are skipped (a
    resale row without numbers tells the viewer nothing to show).
    """
    index: dict[str, dict[str, Any]] = {}
    for item in resale_items:
        key = str(item.get("lot_number") or "").strip()
        if not key:
            continue
        low = _to_price(item.get("est_resale_low"))
        high = _to_price(item.get("est_resale_high"))
        if low is None and high is None:
            # No range at all — nothing to display, treat as not-valued.
            continue
        index[key] = {
            "est_resale_low": low,
            "est_resale_high": high,
            "resale_confidence": _norm_enum(item.get("resale_confidence"), _CONFIDENCE),
            "resale_outlook": _norm_enum(item.get("resale_outlook"), _OUTLOOK),
            # The agent emits `reasoning`; we store it as resale_reasoning.
            "resale_reasoning": (item.get("reasoning") or item.get("resale_reasoning") or None),
        }
    return index


def attach_resale(
    merged_items: list[dict[str, Any]],
    resale_index: dict[str, dict[str, Any]],
) -> int:
    """
    Mutate ``merged_items`` in place, copying resale fields onto each item that
    has a matching resale entry (by lot_number, then by raw id as a fallback).

    Returns the number of lots that received resale data. Lots with no match
    are left untouched, so their resale fields stay at the schema default
    (None) — the viewer renders them with no resale info.
    """
    attached = 0
    for item in merged_items:
        keys = (
            str(item.get("lot_number") or "").strip(),
            str(item.get("id") or "").strip(),
        )
        resale = next((resale_index[k] for k in keys if k and k in resale_index), None)
        if resale is None:
            continue
        item.update(resale)
        attached += 1
    return attached
