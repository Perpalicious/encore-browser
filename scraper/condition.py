"""
Condition and Est. Retail Price extraction from HiBid lot descriptions.

HiBid descriptions embed structured lines like:
    Condition: BRAND NEW - SEALED
    Est. Retail Price: 55.00
    In packaging? Yes
    ...

This module strips those "Key: Value" / "Key? Value" lines, returning:
    - condition: HiBid's own condition string, or None
    - est_retail_price: float or None
    - description_remaining: the free-form text with structured lines removed

Condition is passed through 1:1. It used to be squeezed into five invented
labels ("New", "Like New", "Good", "Fair", "Heavily Used") taken from a design
spec written before anyone had seen real HiBid data — see CC_HANDOFF_BRIEF.md.
That mapping was wrong in both directions. Measured over both auctions of the
week of 2026-08-16 (30,358 lots):

  - "Like New" does not exist on HiBid. Zero occurrences. It was a synthetic
    bucket merging EXCELLENT (11,148 lots) with BRAND NEW - OPEN BOX (5,038) —
    53% of the auction under one label, conflating used-but-great with unused
    open-box merchandise. Those price differently, and because
    tools/slim_resale.py groups on this field, 118 resale groups were valued
    once and fanned out across both conditions.
  - Ten of the twenty-one keys it mapped never appeared at all: LIKE NEW,
    OPEN BOX, NEW IN BOX, BRAND NEW, NEW, VERY GOOD, USED, POOR, DAMAGED,
    NEW ADJUSTED QTY.
  - FOR PARTS ONLY (1,029 lots) became "Heavily Used", losing "not
    functional". BEST BEFORE (GROCERY) became "New", losing the expiry
    caveat. DO NOT BID became null, indistinguishable from "not recorded".

HiBid writes conditions in caps; we store title case and the viewer uppercases
for display, so what renders matches the listing verbatim.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Condition vocabulary
# ---------------------------------------------------------------------------

# HiBid's full observed vocabulary, best → worst, with lot counts across both
# auctions of the week of 2026-08-16 (30,358 lots). This list drives filter-chip
# order and the colour ramp; it is NOT a whitelist. An unrecognised value is
# passed through rather than dropped, so a new HiBid condition shows up in the
# viewer instead of silently becoming null.
CONDITION_LABELS: tuple[str, ...] = (
    "Brand New - Sealed",       # 4,270
    "Brand New - Open Box",     # 5,038
    "New (Adjusted Quantity)",  #   552
    "Best Before (Grocery)",    #   102
    "Excellent",                # 11,148
    "Good",                     # 6,065
    "New With Defects",         #   305
    "Fair",                     # 1,295
    "Heavily Used",             #   494
    "For Parts Only",           # 1,029
    "Do Not Bid",               #    12
)

# Data-entry placeholders — the auction house left the dropdown untouched.
# These mean "no condition recorded", so they resolve to None rather than
# rendering a form prompt as if it were a condition.
_PLACEHOLDER_VALUES: frozenset[str] = frozenset({"SELECT CONDITION HERE"})

# Capitalise each word, leaving punctuation and digits alone. HiBid emits caps
# ("BRAND NEW - SEALED"); this yields "Brand New - Sealed" without str.title()'s
# apostrophe bug ("BAT'S" -> "Bat'S").
_WORD_RE = re.compile(r"[A-Za-z']+")


def canonical_condition(value: str) -> str:
    """Normalise a raw HiBid condition string to its stored form."""
    return _WORD_RE.sub(lambda m: m.group(0).capitalize(), value.strip())


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

        - condition: HiBid's condition string in title case (normally one of
          CONDITION_LABELS, but any unrecognised value is passed through), or
          None when no Condition line is present or it holds a placeholder
        - est_retail_price: float or None
        - description_remaining: free-form text after structured lines stripped (may be "")
    """
    if not raw:
        return None, None, ""

    # HiBid descriptions use \r (lone carriage return) as the line separator.
    # Normalize to \n so the MULTILINE regexes anchor on every line.
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    # --- Extract condition --------------------------------------------------
    condition: Optional[str] = None
    m = _CONDITION_RE.search(raw)
    if m:
        raw_cond = m.group("value").strip()
        # Placeholders mean the dropdown was never filled in; everything else is
        # kept verbatim, including values not yet in CONDITION_LABELS.
        if raw_cond and raw_cond.upper() not in _PLACEHOLDER_VALUES:
            condition = canonical_condition(raw_cond)

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
