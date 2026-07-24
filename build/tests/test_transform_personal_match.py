"""Personal-match fields must carry through to lots when present, and be
absent (None) when the categorized input predates the personal-match pass."""

from __future__ import annotations

from build.transform import transform_all

PERSONAL_FIELDS = {
    "personal_match": True,
    "personal_tags": ["woodworking", "power tools"],
    "match_strength": "strong",
    "match_types": ["hobby", "tool"],
    "personal_reasoning": "Matches the workshop tool interest.",
}


def _shape_a_item(**extra):
    item = {
        "lot_number": "12",
        "title": "Cordless Drill",
        "description": "A drill.",
        "condition": "Good",
        "thumb_url": "https://example.com/t.jpg",
        "image_url": "https://example.com/i.jpg",
        "lot_url": "https://encoreauctions.hibid.com/lot/12",
        "category": "Tools",
        "subcategory": "Power Tools",
        "confidence": "high",
        "is_bats_list": True,
        "bats_buckets": ["Tools"],
        "close_at": "2026-07-20T18:00:00Z",
    }
    item.update(extra)
    return item


def _shape_b_item(**extra):
    item = {
        "lot_number": "34",
        "title": "Hand Saw",
        "description": "A saw.",
        "condition": "Fair",
        "thumb_url": "https://example.com/t2.jpg",
        "image_url": "https://example.com/i2.jpg",
        "url": "https://encoreauctions.hibid.com/lot/34",
        "is_bats_list": True,
        "bats_category": "Tools",
        "bats_subcategory": "Hand Tools",
        "predicted_confidence": 0.9,
        "close_at": "2026-07-20T18:00:00Z",
    }
    item.update(extra)
    return item


def test_shape_a_personal_fields_carry_through():
    (lot,) = transform_all([_shape_a_item(**PERSONAL_FIELDS)])
    assert lot.personal_match is True
    assert lot.personal_tags == ["woodworking", "power tools"]
    assert lot.match_strength == "strong"
    assert lot.match_types == ["hobby", "tool"]
    assert lot.personal_reasoning == "Matches the workshop tool interest."


def test_shape_b_personal_fields_carry_through():
    (lot,) = transform_all([_shape_b_item(**PERSONAL_FIELDS)])
    assert lot.personal_match is True
    assert lot.personal_tags == ["woodworking", "power tools"]
    assert lot.match_strength == "strong"
    assert lot.match_types == ["hobby", "tool"]
    assert lot.personal_reasoning == "Matches the workshop tool interest."


def test_shape_a_without_personal_fields_builds_fine():
    (lot,) = transform_all([_shape_a_item()])
    assert lot.personal_match is None
    assert lot.personal_tags is None
    assert lot.match_strength is None
    assert lot.match_types is None
    assert lot.personal_reasoning is None


def test_shape_b_without_personal_fields_builds_fine():
    (lot,) = transform_all([_shape_b_item()])
    assert lot.personal_match is None
    assert lot.personal_tags is None
    assert lot.match_strength is None
    assert lot.match_types is None
    assert lot.personal_reasoning is None


def test_personal_match_false_carries_through():
    """An explicit False is preserved, not confused with absence."""
    (lot,) = transform_all([_shape_a_item(personal_match=False)])
    assert lot.personal_match is False


def test_bats_fields_unchanged_by_personal_fields():
    """Existing is_bat/bat_buckets behavior is unaffected either way."""
    (with_pm,) = transform_all([_shape_a_item(**PERSONAL_FIELDS)])
    (without,) = transform_all([_shape_a_item()])
    for lot in (with_pm, without):
        assert lot.is_bat is True
        assert lot.bat_buckets == ["Tools"]

    (b_with,) = transform_all([_shape_b_item(**PERSONAL_FIELDS)])
    (b_without,) = transform_all([_shape_b_item()])
    for lot in (b_with, b_without):
        assert lot.is_bat is True
        assert lot.bat_buckets == ["Tools", "Hand Tools"]
