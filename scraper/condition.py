"""
Condition and Est. Retail Price extraction from HiBid lot descriptions.

HiBid descriptions embed structured lines like:
    Condition: BRAND NEW - SEALED
    Est. Retail Price: 55.00
    In packaging? Yes
    ...

This module strips those "Key: Value" / "Key? Value" lines, returning:
    - condition: one of the 5 design labels, or None
    - est_retail_price: float or None
    - description_remaining: the free-form text with structured lines removed
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Condition mapping (case-insensitive key lookup)
# ---------------------------------------------------------------------------

_CONDITION_MAP: dict[str, str] = {
    "BRAND NEW - SEALED": "New",
    "BRAND NEW": "New",
    "NEW IN BOX": "New",
    "NEW": "New",
    "LIKE NEW": "Like New",
    "OPEN BOX": "Like New",
    "EXCELLENT": "Like New",
    "GOOD": "Good",
    "VERY GOOD": "Good",
    "FAIR": "Fair",
    "USED": "Fair",
    "HEAVILY USED": "Heavily Used",
    "POOR": "Heavily Used",
    "DAMAGED": "Heavily Used",
}

# Normalised lookup (upper-cased keys already, but normalise at call site too)
_CONDITION_LOOKUP: dict[str, str] = {k.upper(): v for k, v in _CONDITION_MAP.items()}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# A "structured line" is any line of the form:
#   Key: Value
#   Key? Value
# where Key contains only letters, digits, spaces, dots, hyphens, apostrophes.
# We capture the label and the value separately.
_STRUCTURED_LINE_RE = re.compile(
    r"^(?P<label>[A-Za-z0-9 .'\-]+[?:])\s*(?P<value>.*)$",
    re.MULTILINE,
)

# Specific extractors
_CONDITION_RE = re.compile(
    r"^Condition:\s*(?P<value>.+)$",
    re.MULTILINE | re.IGNORECASE,
)

_RETAIL_PRICE_RE = re.compile(
    r"^Est\.\s*Retail\s*Price:\s*\$?(?P<value>[\d,]+(?:\.\d+)?)$",
    re.MULTILINE | re.IGNORECASE,
)


def parse_condition(raw: Optional[str]) -> tuple[Optional[str], Optional[float], str]:
    """
    Parse a HiBid lot description.

    Returns:
        (condition, est_retail_price, description_remaining)

        - condition: one of "New" | "Like New" | "Good" | "Fair" | "Heavily Used" | None
        - est_retail_price: float or None
        - description_remaining: free-form text after structured lines stripped (may be "")
    """
    if not raw:
        return None, None, ""

    # --- Extract condition --------------------------------------------------
    condition: Optional[str] = None
    m = _CONDITION_RE.search(raw)
    if m:
        raw_cond = m.group("value").strip().upper()
        # Try exact match first, then longest-prefix match for safety
        condition = _CONDITION_LOOKUP.get(raw_cond)
        if condition is None:
            # Fall through — unknown value maps to None per spec
            pass

    # --- Extract retail price -----------------------------------------------
    est_retail_price: Optional[float] = None
    m2 = _RETAIL_PRICE_RE.search(raw)
    if m2:
        try:
            est_retail_price = float(m2.group("value").replace(",", ""))
        except ValueError:
            est_retail_price = None

    # --- Strip structured lines ---------------------------------------------
    # Remove all lines that match the "Label: Value" or "Label? Value" pattern.
    lines = raw.splitlines()
    remaining_lines = [
        line for line in lines if not _STRUCTURED_LINE_RE.match(line.strip())
    ]
    description_remaining = "\n".join(remaining_lines).strip()

    return condition, est_retail_price, description_remaining
