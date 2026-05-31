"""
Tests for build/resale.py — joining the optional resale-valuation file onto
the merged lots, and for the resale fields surviving the transform/validate
pass. Covers:
  - build_resale_index normalises confidence/outlook and coerces prices
  - rows with no usable low/high range are skipped
  - attach_resale fills matched lots and leaves unmatched lots untouched
  - matching by lot_number, with raw-id fallback
  - missing resale data never crashes; transform yields None resale fields
  - a full transform of a resale-joined item validates against the Lot schema
"""

from __future__ import annotations

from build.resale import build_resale_index, attach_resale
from build.transform import transform_item
from build.schema import Lot


def _merged(lot_number, **extra):
    """A minimal merged item (post-merge, pre-transform) shaped like Shape B."""
    base = {
        "lot_number": lot_number,
        "id": f"id-{lot_number}",
        "title": f"Lot {lot_number}",
        "description": "",
        "thumb_url": "",
        "image_url": "",
        "lot_url": "https://encoreauctions.hibid.com/lot/1/x",
        "condition": None,
        "category_path": ["Tools", "Hand Tools"],
        "bats_category": "",
        "bats_subcategory": "",
        "predicted_confidence": 0.5,
        "est_retail_price": 120.0,
    }
    base.update(extra)
    return base


def test_index_normalises_enums_and_coerces_prices():
    index = build_resale_index(
        [
            {
                "lot_number": "1a",
                "est_resale_low": "40",  # string → float
                "est_resale_high": 70,
                "resale_confidence": "HIGH",  # uppercased → normalised
                "resale_outlook": " Good ",  # whitespace → normalised
                "reasoning": "Sells well.",
            }
        ]
    )
    entry = index["1a"]
    assert entry["est_resale_low"] == 40.0
    assert entry["est_resale_high"] == 70.0
    assert entry["resale_confidence"] == "high"
    assert entry["resale_outlook"] == "good"
    assert entry["resale_reasoning"] == "Sells well."


def test_index_nulls_unknown_enum_values():
    index = build_resale_index(
        [{"lot_number": "1", "est_resale_low": 10, "est_resale_high": 20,
          "resale_confidence": "very-high", "resale_outlook": "meh"}]
    )
    assert index["1"]["resale_confidence"] is None
    assert index["1"]["resale_outlook"] is None


def test_index_skips_rows_without_a_range():
    index = build_resale_index(
        [
            {"lot_number": "1", "resale_confidence": "high"},  # no low/high
            {"lot_number": "2", "est_resale_low": None, "est_resale_high": ""},
            {"lot_number": "3", "est_resale_low": 5},  # one bound is enough
        ]
    )
    assert "1" not in index
    assert "2" not in index
    assert "3" in index


def test_attach_fills_matches_and_leaves_others_untouched():
    merged = [_merged("1a"), _merged("2b")]
    index = build_resale_index(
        [{"lot_number": "1a", "est_resale_low": 40, "est_resale_high": 70,
          "resale_confidence": "medium", "resale_outlook": "good",
          "reasoning": "x"}]
    )
    attached = attach_resale(merged, index)
    assert attached == 1
    assert merged[0]["est_resale_low"] == 40.0
    assert merged[0]["resale_outlook"] == "good"
    # Unmatched lot keeps no resale keys at all.
    assert "est_resale_low" not in merged[1]


def test_attach_matches_by_raw_id_fallback():
    merged = [_merged("display-1")]  # id == "id-display-1"
    index = build_resale_index(
        [{"lot_number": "id-display-1", "est_resale_low": 5, "est_resale_high": 9}]
    )
    attached = attach_resale(merged, index)
    assert attached == 1
    assert merged[0]["est_resale_high"] == 9.0


def test_missing_resale_transforms_to_none_fields():
    """A lot never seen by the valuation pass validates with None resale fields."""
    lot = Lot(**transform_item(_merged("1a")))
    assert lot.est_resale_low is None
    assert lot.est_resale_high is None
    assert lot.resale_confidence is None
    assert lot.resale_outlook is None
    assert lot.resale_reasoning is None
    # Estimated retail still comes through from the raw scrape.
    assert lot.est_retail_price == 120.0


def test_full_join_then_transform_validates():
    merged = [_merged("1a")]
    index = build_resale_index(
        [{"lot_number": "1a", "est_resale_low": 40, "est_resale_high": 70,
          "resale_confidence": "high", "resale_outlook": "good",
          "reasoning": "Comparable units resell steadily."}]
    )
    attach_resale(merged, index)
    lot = Lot(**transform_item(merged[0]))
    assert lot.est_resale_low == 40.0
    assert lot.est_resale_high == 70.0
    assert lot.resale_confidence == "high"
    assert lot.resale_outlook == "good"
    assert lot.resale_reasoning == "Comparable units resell steadily."
    assert lot.est_retail_price == 120.0


def test_empty_resale_index_attaches_nothing():
    merged = [_merged("1a"), _merged("2b")]
    assert attach_resale(merged, {}) == 0
    assert all("est_resale_low" not in m for m in merged)
