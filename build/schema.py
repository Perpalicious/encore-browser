"""Pydantic schema for the Lot output shape."""

from typing import Literal, Optional
from pydantic import BaseModel, field_validator

from scraper.condition import CONDITION_LABELS


# HiBid's own condition vocabulary, passed through 1:1 by scraper/condition.py.
# Kept as a plain set, not a Literal: an unrecognised value must reach the
# viewer rather than fail the build, so a condition HiBid adds later shows up
# instead of vanishing. build/transform.py warns on anything outside this set.
VALID_CONDITIONS = set(CONDITION_LABELS)
VALID_CONFIDENCES = {"low", "medium", "high"}


class Lot(BaseModel):
    day: str
    lot_number: str
    title: str
    description: str
    condition: Optional[str]
    thumb_url: str
    image_url: str
    lot_url: str
    category: str
    subcategory: str
    category_path: list[str]
    is_bat: bool
    bat_buckets: list[str]
    confidence: Literal["low", "medium", "high"]

    # --- Closing time (from the scraper, may be missing) --------------------
    # ISO-8601 with an explicit UTC offset, parsed from HiBid's timeLeftTitle
    # by scraper/parser.py. None on older bundles and on any lot whose
    # timeLeftTitle could not be parsed.
    close_at: Optional[str] = None

    # --- Bat's List subtype (optional, from the flagging pass) --------------
    # Free-form 1-3 words under the fixed bucket, e.g. "scrub brushes" inside
    # "Cleaning supplies & tools". Normalised in transform. None when the lot
    # is unflagged or the pass predates the key.
    bat_subtype: Optional[str] = None

    # --- Estimated retail (from the scraper, may be missing) ----------------
    # The lot's estimated retail price as listed by HiBid. None when the
    # scraper could not extract one.
    est_retail_price: Optional[float] = None

    # --- Resale valuation (optional, from the resale agent) -----------------
    # Joined in by `python -m build --resale ...`. Every field is None for the
    # (possibly large) subset of lots the valuation pass did not cover. The
    # viewer shows resale info only when est_resale_low/high are both present.
    est_resale_low: Optional[float] = None
    est_resale_high: Optional[float] = None
    resale_confidence: Optional[Literal["low", "medium", "high"]] = None
    resale_outlook: Optional[Literal["good", "fair", "poor"]] = None
    resale_reasoning: Optional[str] = None

    # --- Personal match (optional, from the personal-match pass) ------------
    # Present only when the categorized input carries personal-match fields.
    # Older categorized files lack them entirely; every field stays None then.
    personal_match: Optional[bool] = None
    personal_tags: Optional[list[str]] = None
    match_strength: Optional[str] = None
    match_types: Optional[list[str]] = None
    personal_reasoning: Optional[str] = None

    @field_validator("lot_number", "title", "description", "lot_url", "category",
                     "subcategory", "thumb_url", "image_url",
                     mode="before")
    @classmethod
    def must_be_str(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError(f"expected str, got {type(v).__name__}: {v!r}")
        return v

    @field_validator("bat_buckets", "category_path", mode="before")
    @classmethod
    def must_be_list_of_str(cls, v: object) -> list:
        if not isinstance(v, list):
            raise ValueError(f"expected list, got {type(v).__name__}: {v!r}")
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"list items must be str, got {type(item).__name__}: {item!r}")
        return v
