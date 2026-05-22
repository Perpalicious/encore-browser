"""Tests for Shape A (brief's idealized schema) transform."""

from __future__ import annotations

import pytest
from build.transform import transform_item, transform_all
from build.schema import Lot


SHAPE_A_MINIMAL = {
    "lot_number": "0142",
    "title": "Vintage Lamp",
    "description": "A nice lamp",
    "condition": "Good",
    "thumb_url": "https://cdn.example.com/thumb_142.jpg",
    "image_url": "https://cdn.example.com/img_142.jpg",
    "lot_url": "https://encoreauctions.hibid.com/lot/142/?ref=catalog",
    "close_at": "2026-05-24T17:00:00+00:00",
    "hibid_category_leaf": "Lamps",
    "hibid_category_path": "Home > Lamps",
    "category": "Home & Garden",
    "subcategory": "Lighting",
    "confidence": "medium",
    "is_bats_list": True,
    "bats_buckets": ["Home Decor", "Lighting"],
    "is_nice_pick": True,
    "nice_pick_reason": "Great vintage find",
}

SHAPE_A_MINIMAL_NO_OPTIONAL = {
    "lot_number": "0099",
    "title": "Mystery Box",
    "description": "",
    "lot_url": "https://encoreauctions.hibid.com/lot/99/?ref=catalog",
    "category": "Uncategorized",
    "subcategory": "",
    "confidence": "low",
    "is_bats_list": False,
    "bats_buckets": [],
    "is_nice_pick": False,
    "nice_pick_reason": "",
}


def test_shape_a_basic_transform():
    raw = transform_item(SHAPE_A_MINIMAL)
    lot = Lot(**raw)
    assert lot.lot_number == "0142"
    assert lot.title == "Vintage Lamp"
    assert lot.condition == "Good"
    assert lot.is_bat is True
    assert lot.bat_buckets == ["Home Decor", "Lighting"]
    assert lot.is_nice_pick is True
    assert lot.nice_pick_reason == "Great vintage find"
    assert lot.confidence == "medium"
    assert lot.subcategory == "Lighting"
    assert lot.category == "Home & Garden"
    assert lot.lot_url == "https://encoreauctions.hibid.com/lot/142/?ref=catalog"


def test_shape_a_day_derived_from_close_at():
    raw = transform_item(SHAPE_A_MINIMAL)
    lot = Lot(**raw)
    # 2026-05-24 is a Sunday
    assert lot.day == "Sunday"


def test_shape_a_minimal_no_optional():
    raw = transform_item(SHAPE_A_MINIMAL_NO_OPTIONAL)
    lot = Lot(**raw)
    assert lot.is_bat is False
    assert lot.bat_buckets == []
    assert lot.is_nice_pick is False
    assert lot.condition is None
    assert lot.thumb_url == ""
    assert lot.image_url == ""


def test_shape_a_bats_buckets_deduped():
    item = {**SHAPE_A_MINIMAL, "bats_buckets": ["Home", "Home", "Lighting"]}
    raw = transform_item(item)
    lot = Lot(**raw)
    assert lot.bat_buckets == ["Home", "Lighting"]


def test_shape_a_confidence_float_bucketed():
    item = {**SHAPE_A_MINIMAL, "confidence": 0.8}
    raw = transform_item(item)
    lot = Lot(**raw)
    assert lot.confidence == "high"


def test_shape_a_confidence_low_bucket():
    item = {**SHAPE_A_MINIMAL, "confidence": 0.1}
    raw = transform_item(item)
    lot = Lot(**raw)
    assert lot.confidence == "low"


def test_shape_a_confidence_medium_bucket():
    item = {**SHAPE_A_MINIMAL, "confidence": 0.5}
    raw = transform_item(item)
    lot = Lot(**raw)
    assert lot.confidence == "medium"


def test_transform_all_shape_a_returns_lots():
    lots = transform_all([SHAPE_A_MINIMAL, SHAPE_A_MINIMAL_NO_OPTIONAL])
    assert len(lots) == 2
    assert all(isinstance(lot, Lot) for lot in lots)


def test_shape_a_null_condition_passthrough():
    item = {**SHAPE_A_MINIMAL, "condition": None}
    raw = transform_item(item)
    lot = Lot(**raw)
    assert lot.condition is None
