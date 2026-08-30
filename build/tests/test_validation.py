"""Tests that invalid input causes exit 1 with a useful error message."""

from __future__ import annotations

import sys
import pytest
from unittest.mock import patch
from build.transform import transform_all


VALID_SHAPE_B = {
    "lot_number": "123",
    "title": "Test Item",
    "description": "A description",
    "url": "https://encoreauctions.hibid.com/lot/123/test-item?ref=catalog",
    "image_url": "",
    "day": "Sunday",
    "category": "Electronics",
    "is_bats_list": False,
    "bats_category": "",
    "bats_subcategory": "",
    "is_nice_pick": False,
    "nice_pick_category": "",
    "nice_pick_subcategory": "",
    "predicted_confidence": 0.0,
}


def test_valid_item_does_not_exit():
    """A valid item should transform without raising SystemExit."""
    lots = transform_all([VALID_SHAPE_B])
    assert len(lots) == 1


def test_invalid_confidence_string_coerced():
    """An unknown confidence string should default to 'low' gracefully."""
    item = {
        **VALID_SHAPE_B,
        # Remove predicted_confidence to force missing-field handling
    }
    item_no_conf = {k: v for k, v in item.items() if k != "predicted_confidence"}
    lots = transform_all([item_no_conf])
    assert lots[0].confidence == "low"


def test_is_bat_must_be_bool_coercible():
    """is_bats_list truthy/falsy values should be correctly coerced to bool."""
    item_truthy = {**VALID_SHAPE_B, "is_bats_list": 1}
    item_falsy = {**VALID_SHAPE_B, "is_bats_list": 0}
    lots_t = transform_all([item_truthy])
    lots_f = transform_all([item_falsy])
    assert lots_t[0].is_bat is True
    assert lots_f[0].is_bat is False


def test_unknown_condition_value_passes_through():
    """A condition outside the known vocabulary must reach the bundle.

    Conditions are HiBid's own strings, stored 1:1 rather than mapped onto a
    fixed set. If HiBid adds a grading, failing the build (or nulling the field)
    would hide it; instead it ships, build/__main__.py warns, and the viewer
    gives it the neutral colour until it's added to CONDITION_LABELS.
    """
    item = {**VALID_SHAPE_B, "condition": "Refurbished"}
    lots = transform_all([item])
    assert lots[0].condition == "Refurbished"


def test_known_condition_value_survives_transform():
    item = {**VALID_SHAPE_B, "condition": "Brand New - Open Box"}
    lots = transform_all([item])
    assert lots[0].condition == "Brand New - Open Box"


def test_missing_required_title_exits_1(capsys):
    """A missing title field should cause exit 1 after transform sets it to ''."""
    # title="" is actually valid per schema (empty string). The schema doesn't enforce
    # non-empty strings except through type. But let's verify that passing a non-string
    # title causes a failure.
    item = {**VALID_SHAPE_B, "title": 12345}
    # transform does: title = item.get("title") or "" → 12345 is truthy so title=12345
    # schema validator must_be_str will catch this.
    with pytest.raises(SystemExit) as exc_info:
        transform_all([item])
    assert exc_info.value.code == 1


def test_error_message_includes_lot_number(capsys):
    """Error output must include the lot_number of the failing item."""
    item = {**VALID_SHAPE_B, "title": 99999, "lot_number": "LOT-XYZ"}
    with pytest.raises(SystemExit):
        transform_all([item])
    captured = capsys.readouterr()
    assert "LOT-XYZ" in captured.err


def test_error_message_includes_field_name(capsys):
    """Error output must include the offending field name."""
    item = {**VALID_SHAPE_B, "title": 99999}
    with pytest.raises(SystemExit):
        transform_all([item])
    captured = capsys.readouterr()
    assert "title" in captured.err


def test_error_message_includes_item_index(capsys):
    """Error output must include the item index."""
    good = VALID_SHAPE_B.copy()
    bad = {**VALID_SHAPE_B, "title": 99999}
    with pytest.raises(SystemExit):
        transform_all([good, bad])
    captured = capsys.readouterr()
    assert "index 1" in captured.err


def test_bat_buckets_invalid_type_exits_1():
    """bat_buckets must be a list — if the transform produces something else, exit 1."""
    # We test the schema directly here
    from build.schema import Lot
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Lot(
            day="Sunday",
            lot_number="1",
            title="X",
            description="",
            condition=None,
            thumb_url="",
            image_url="",
            lot_url="https://encoreauctions.hibid.com/lot/1/x",
            category="",
            subcategory="",
            category_path=[],
            is_bat=False,
            bat_buckets="not-a-list",  # type: ignore
            confidence="low",
        )
