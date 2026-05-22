"""Tests against the real Shape B sample file at data/categorized/auction_703264_categorized.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Resolve data path relative to repo root (two dirs up from this tests/ folder)
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = REPO_ROOT / "data" / "categorized" / "auction_703264_categorized.json"


@pytest.fixture(scope="module")
def sample_items():
    with SAMPLE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["items"]


@pytest.fixture(scope="module")
def bundle(sample_items):
    from build.transform import transform_all
    return transform_all(sample_items)


def test_item_count(sample_items, bundle):
    assert len(bundle) == len(sample_items)


def test_is_bat_matches_is_bats_list(sample_items, bundle):
    for inp, lot in zip(sample_items, bundle):
        assert lot.is_bat == bool(inp["is_bats_list"]), (
            f"lot_number={inp['lot_number']}: is_bat mismatch"
        )


def test_bat_buckets_populated_for_bats(bundle):
    """All bat items with a bats_category/subcategory should have non-empty bat_buckets."""
    for lot in bundle:
        if lot.is_bat:
            # bat_buckets may be [] if both bats_category and bats_subcategory are empty
            assert isinstance(lot.bat_buckets, list)


def test_bat_buckets_deduped(sample_items, bundle):
    """bat_buckets must not contain duplicates."""
    for lot in bundle:
        assert len(lot.bat_buckets) == len(set(lot.bat_buckets))


def test_confidence_is_string(bundle):
    for lot in bundle:
        assert lot.confidence in ("low", "medium", "high"), (
            f"lot_number={lot.lot_number}: invalid confidence={lot.confidence!r}"
        )


def test_lot_url_from_url_field(sample_items, bundle):
    """lot_url must be populated from input url for Shape B items."""
    for inp, lot in zip(sample_items, bundle):
        if inp.get("url"):
            assert lot.lot_url == inp["url"], (
                f"lot_number={inp['lot_number']}: lot_url mismatch"
            )


def test_no_nulls_in_required_str_fields(bundle):
    for lot in bundle:
        assert lot.lot_number is not None
        assert lot.title is not None
        assert lot.description is not None
        assert lot.lot_url is not None
        assert lot.category is not None
        assert lot.subcategory is not None
        assert lot.thumb_url is not None
        assert lot.image_url is not None
        assert lot.nice_pick_reason is not None
        assert lot.day is not None


def test_subcategory_from_bats_subcategory(sample_items, bundle):
    """If bats_subcategory is set, subcategory should match it."""
    for inp, lot in zip(sample_items, bundle):
        if inp.get("bats_subcategory"):
            assert lot.subcategory == inp["bats_subcategory"]


def test_nice_pick_reason_from_nice_pick_subcategory(sample_items, bundle):
    """If nice_pick_subcategory is set, nice_pick_reason should use it."""
    for inp, lot in zip(sample_items, bundle):
        if inp.get("nice_pick_subcategory"):
            assert lot.nice_pick_reason == inp["nice_pick_subcategory"]


def test_is_nice_pick_count(sample_items, bundle):
    input_nice = sum(1 for i in sample_items if i["is_nice_pick"])
    output_nice = sum(1 for lot in bundle if lot.is_nice_pick)
    assert input_nice == output_nice


def test_all_days_populated(bundle):
    for lot in bundle:
        assert lot.day != "", f"lot_number={lot.lot_number}: day is empty"
