"""The canonical flagging-row contract.

Everything that touches a flagging row derives from this module: validation of
worker responses, expansion of `no_match` into all-false rows, what `finalize`
writes, the tests, and — by import — `tools/prefilter.py`'s `BASE_ROW` and
`tools/verify_passes.py`'s required-field sets.

Why one module rather than the obvious per-file constants
---------------------------------------------------------
The field names here are load-bearing in ways that fail silently. A row that
says `reasoning` instead of `personal_reasoning` is dropped by
`build/transform.py` without complaint. A stray `bats_category` key flips that
same module into "Shape B" and makes it ignore `bats_buckets` entirely, so
every lot arrives in the viewer with no buckets. A non-match row that omits
`bats_buckets` replaces the base row via `merge_categorized` (whole-row
replace) and deletes the field.

Each of those is a one-word difference that produces a complete, plausible,
wrong bundle. Keeping the names in one place is what stops the prompt, the
validator and the writer from drifting apart.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, model_validator

# Bumping this invalidates every previously ingested chunk through the run
# fingerprint (see classify/provenance.py), which is the point: a contract
# change must not be able to blend with results produced under the old one.
CONTRACT_VERSION = "flagging-v1"

# Every non-matching lot gets exactly this row, with lot_number filled in.
# Four keys, because `merge_categorized` replaces whole rows: a shorter row
# would drop bats_buckets/personal_match and turn personal_match into null in
# the bundle. `tools/prefilter.py` imports this.
BASE_ROW: dict = {"is_bats_list": False, "bats_buckets": [], "personal_match": False}

# Consumed by tools/verify_passes.py. `resale` is unchanged and unused by the
# flagging automation; it lives here so the two required-field sets stay in one
# place rather than drifting apart in two files.
REQUIRED_FIELDS: dict[str, set[str]] = {
    "categorized": {"lot_number", "is_bats_list", "bats_buckets", "personal_match"},
    "resale": {"lot_number", "est_resale_low", "est_resale_high"},
}

# Keys that must never appear. `bats_category` is the dangerous one — see the
# module docstring — but all six are rejected so a near-miss key name cannot
# quietly ride along.
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {"bats_category", "bats_subcategory", "category", "subcategory",
     "reasoning", "confidence"}
)

# Present only on rows where personal_match is true.
PERSONAL_ONLY_KEYS: tuple[str, ...] = (
    "personal_tags", "match_strength", "match_types", "personal_reasoning",
)

MATCH_STRENGTHS: frozenset[str] = frozenset({"strong", "moderate", "weak"})

# A subtype is meant to be a 1-3 word navigation label. More than this is a
# sentence, which makes the drill-down unusable; the softer 3-word guidance is
# reported as a warning rather than enforced, so an occasional four-word label
# does not trigger a re-dispatch.
SUBTYPE_MAX_WORDS = 5
SUBTYPE_WARN_WORDS = 3


class MatchRow(BaseModel):
    """A lot that is on Bat's List, is a personal pick, or both.

    `extra="forbid"` is what structurally rejects FORBIDDEN_KEYS and any typo'd
    field, rather than relying on a hand-maintained blocklist.
    """

    model_config = ConfigDict(extra="forbid")

    lot_number: StrictStr
    # StrictBool so the string "true" and the integer 1 are rejected rather
    # than coerced — PROMPTS.md calls this out because only a real boolean
    # counts as a pick downstream.
    is_bats_list: StrictBool
    bats_buckets: list[StrictStr]
    personal_match: StrictBool

    bats_subtype: Optional[StrictStr] = None
    personal_tags: Optional[list[StrictStr]] = None
    match_strength: Optional[Literal["strong", "moderate", "weak"]] = None
    match_types: Optional[list[StrictStr]] = None
    personal_reasoning: Optional[StrictStr] = None

    @model_validator(mode="after")
    def _check_invariants(self) -> "MatchRow":
        if self.is_bats_list != bool(self.bats_buckets):
            raise ValueError(
                "is_bats_list must equal (bats_buckets is non-empty); got "
                f"is_bats_list={self.is_bats_list!r} with {len(self.bats_buckets)} buckets"
            )

        if self.is_bats_list and not (self.bats_subtype or "").strip():
            raise ValueError("bats_subtype is required when is_bats_list is true")
        if not self.is_bats_list and self.bats_subtype is not None:
            raise ValueError("bats_subtype must be omitted when is_bats_list is false")

        # A blank subtype is already unreachable here: on a flagged row the
        # `required` check above catches it, and on an unflagged row the
        # `must be omitted` check does.
        if self.bats_subtype is not None:
            words = self.bats_subtype.split()
            if len(words) > SUBTYPE_MAX_WORDS:
                raise ValueError(
                    f"bats_subtype {self.bats_subtype!r} is {len(words)} words; "
                    f"it is a label, not a sentence (max {SUBTYPE_MAX_WORDS})"
                )

        if not self.personal_match:
            present = [k for k in PERSONAL_ONLY_KEYS if getattr(self, k) is not None]
            if present:
                raise ValueError(
                    f"{present} must be omitted when personal_match is false"
                )

        if not self.is_bats_list and not self.personal_match:
            raise ValueError(
                "row matches nothing — a lot that is neither on Bat's List nor a "
                "personal pick belongs in no_match, not matches"
            )
        return self

    def to_row(self) -> dict:
        """The dict written to `_flags_<x>.json`.

        Keys that are None are dropped, so the output is shaped exactly like
        the hand-pasted files this replaces.
        """
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ChunkResponse(BaseModel):
    """The envelope a worker writes for one chunk."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: StrictStr
    fingerprint: StrictStr
    buckets_seen: int
    matches: list[MatchRow]
    no_match: list[StrictStr]


def base_row(lot_number: str) -> dict:
    """The all-false row for a lot that matched nothing."""
    return dict(BASE_ROW, lot_number=lot_number)


def expand(response: ChunkResponse) -> list[dict]:
    """Every lot in the chunk as a full row: matches plus expanded no_match.

    This is where the compact `no_match` array becomes the four-key rows the
    rest of the pipeline expects, so `finalize` writes a file identical in
    shape to the manual flow's output.
    """
    return [m.to_row() for m in response.matches] + [
        base_row(n) for n in response.no_match
    ]
