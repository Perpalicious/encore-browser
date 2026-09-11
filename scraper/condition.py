"""
Condition extraction from HiBid lot descriptions.

HiBid descriptions embed structured lines like:
    Condition: BRAND NEW - SEALED
    In packaging? Yes
    ...

This module strips those "Key: Value" / "Key? Value" lines, returning:
    - condition: HiBid's own condition string, or None
    - description_remaining: the free-form text with structured lines removed

`Est. Retail Price:` used to be parsed out of here too, as
`est_retail_price`. It was dropped on 2026-09-10 — see the note at the bottom
of this docstring.

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

Why `est_retail_price` is gone (2026-09-10)
-------------------------------------------
It was parsed from an `Est. Retail Price:` line and carried all the way to the
viewer, where it was displayed on every card, was one of the sort orders, and
was the denominator of the "top-decile spread" value badge.

Two reasons it went:

  1. It stopped existing. HiBid moved the structured lot detail into a per-lot
     report image during the week of 2026-08-30, the same change that emptied
     `model`, `size`, `notes` and the damage flags (see tools/slim.py).
     Coverage went 27,011/27,023 on the week of 2026-08-16 to 0/25,195 and then
     0/22,692 — so the viewer had been displaying nothing, sorting on nulls and
     badging no lots for two weeks before anyone noticed
     (data/Watch/FINDINGS.md §4).
  2. It was never a price anyone paid. It is the auction house's own retail
     reference, self-reported and unverified, and the resale pass estimates
     what a lot is actually worth. Keeping a second, weaker money figure beside
     it invited the comparison.

Removing it is deliberate, not a reaction to the parse breaking. If HiBid ever
restores the line, do NOT re-add this silently — the field's absence is now a
product decision.

Note that dropping the extraction does not change `description_remaining`: the
retail line is stripped by the generic `_STRUCTURED_LINE_RE` pass below, which
removes every "Label: Value" line whether or not anything reads it.
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

def parse_condition(raw: Optional[str]) -> tuple[Optional[str], str]:
    """
    Parse a HiBid lot description.

    Returns:
        (condition, description_remaining)

        - condition: HiBid's condition string in title case (normally one of
          CONDITION_LABELS, but any unrecognised value is passed through), or
          None when no Condition line is present or it holds a placeholder
        - description_remaining: free-form text after structured lines stripped (may be "")
    """
    if not raw:
        return None, ""

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

    # --- Strip structured lines ---------------------------------------------
    # Remove all lines that match the "Label: Value" or "Label? Value" pattern.
    lines = raw.splitlines()
    remaining_lines = [
        line for line in lines if not _STRUCTURED_LINE_RE.match(line.strip())
    ]
    description_remaining = "\n".join(remaining_lines).strip()

    return condition, description_remaining
