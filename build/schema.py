"""Pydantic schema for the Lot output shape."""

from typing import Literal, Optional
from pydantic import BaseModel, field_validator


VALID_CONDITIONS = {"New", "Like New", "Good", "Fair", "Heavily Used"}
VALID_CONFIDENCES = {"low", "medium", "high"}


class Lot(BaseModel):
    day: str
    lot_number: str
    title: str
    description: str
    condition: Optional[Literal["New", "Like New", "Good", "Fair", "Heavily Used"]]
    thumb_url: str
    image_url: str
    lot_url: str
    category: str
    subcategory: str
    category_path: list[str]
    is_bat: bool
    bat_buckets: list[str]
    confidence: Literal["low", "medium", "high"]

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
