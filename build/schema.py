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
    is_bat: bool
    bat_buckets: list[str]
    is_nice_pick: bool
    nice_pick_reason: str
    confidence: Literal["low", "medium", "high"]

    @field_validator("lot_number", "title", "description", "lot_url", "category",
                     "subcategory", "nice_pick_reason", "thumb_url", "image_url",
                     mode="before")
    @classmethod
    def must_be_str(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError(f"expected str, got {type(v).__name__}: {v!r}")
        return v

    @field_validator("bat_buckets", mode="before")
    @classmethod
    def must_be_list_of_str(cls, v: object) -> list:
        if not isinstance(v, list):
            raise ValueError(f"expected list, got {type(v).__name__}: {v!r}")
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"bat_buckets items must be str, got {type(item).__name__}: {item!r}")
        return v
