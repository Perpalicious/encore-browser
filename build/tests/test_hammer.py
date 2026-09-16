"""
Tests for build/hammer.py — joining past auctions' hammer prices onto this
week's lots, and for `hammer_key` surviving transform/validate. Covers:
  - the product key matches tools/slim_resale.group_key on title + condition
  - weeks are ordered newest-first and capped at MAX_WEEKS
  - an unreadable or wrong-shaped file is skipped with a warning, not fatal
  - only keys some lot references are shipped
  - the bundle carries a `hammer` map iff --hammer was passed, and every
    `hammer_key` on a lot resolves inside it
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from build.hammer import (
    CONDITION_LADDER,
    MAX_WEEKS,
    alt_key_order,
    attach_hammer,
    build_hammer_index,
    count_alt_only,
    describe,
    hammer_key,
    load_hammer_files,
    used_index,
)
from build.transform import transform_item
from build.schema import Lot

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))


def _product(title="SHARK HD430C FLEXSTYLE", condition="Excellent", **extra):
    base = {
        "title": title,
        "condition": condition,
        "sold": 6,
        "unsold": 3,
        "median": 14.0,
        "low": 9.0,
        "high": 22.0,
        "prices": [9.0, 11.0, 13.0, 15.0, 18.0, 22.0],
    }
    base.update(extra)
    return base


def _file(close_date, products, auction_id=1):
    return {
        "auction_id": auction_id,
        "auction_name": f"Auction {auction_id}",
        "close_date": close_date,
        "pulled_at": "2026-09-16T03:12:00+00:00",
        "lots_seen": 100,
        "products": products,
    }


def _merged(lot_number, **extra):
    """A minimal merged item (post-merge, pre-transform) shaped like Shape B."""
    base = {
        "lot_number": lot_number,
        "id": f"id-{lot_number}",
        "title": "SHARK HD430C FLEXSTYLE",
        "description": "",
        "thumb_url": "",
        "image_url": "",
        "lot_url": "https://encoreauctions.hibid.com/lot/1/x",
        "condition": "Excellent",
        "category_path": ["Tools", "Hand Tools"],
        "bats_category": "",
        "bats_subcategory": "",
        "predicted_confidence": 0.5,
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# The key
# ---------------------------------------------------------------------------


class TestKey:
    def test_matches_slim_resale_group_key_on_title_and_condition(self):
        # The hammer join has to group products exactly the way the resale pass
        # does, or a product would be "the same" for one and not the other.
        from slim_resale import group_key

        rec = {"title": " shark hd430c flexstyle ", "condition": "Excellent"}
        title_part, *value_parts = group_key(rec)
        condition_part = value_parts[2]  # VALUE_FIELDS: model, size, condition, …

        assert hammer_key(rec["title"], rec["condition"]) == (
            f"{title_part}|{condition_part}"
        )

    def test_absent_condition_still_yields_a_usable_key(self):
        assert hammer_key("WIDGET", None) == "WIDGET|"

    def test_key_is_case_and_whitespace_insensitive(self):
        assert hammer_key(" Shark ", " excellent ") == hammer_key("SHARK", "EXCELLENT")


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class TestIndex:
    def test_recency_wins__index_zero_is_the_most_recent_week(self, tmp_path):
        (tmp_path / "2026-09-06_1.json").write_text(
            json.dumps(_file("2026-09-06", [_product(median=20.0)]))
        )
        (tmp_path / "2026-09-13_2.json").write_text(
            json.dumps(_file("2026-09-13", [_product(median=14.0)], auction_id=2))
        )
        # Written oldest-first on purpose: order must come from close_date, not
        # from the filesystem.
        index = build_hammer_index(load_hammer_files(tmp_path))
        weeks = index[hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")]
        assert [w["close_date"] for w in weeks] == ["2026-09-13", "2026-09-06"]
        assert weeks[0]["median"] == 14.0

    def test_history_is_capped_at_eight_weeks(self):
        files = [
            _file(f"2026-0{m}-01", [_product(median=float(m))], auction_id=m)
            for m in range(9, 0, -1)
        ]
        index = build_hammer_index(files)
        weeks = index[hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")]
        assert len(weeks) == MAX_WEEKS
        # The eight kept are the eight the caller handed over first.
        assert weeks[0]["close_date"] == "2026-09-01"
        assert weeks[-1]["close_date"] == "2026-02-01"

    def test_a_week_carries_counts_and_figures_but_never_the_price_list(self):
        index = build_hammer_index([_file("2026-09-13", [_product()])])
        week = index[hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")][0]
        assert week == {
            "close_date": "2026-09-13",
            "sold": 6,
            "unsold": 3,
            "median": 14.0,
            "low": 9.0,
            "high": 22.0,
        }

    def test_a_product_that_sold_nothing_keeps_null_figures(self):
        index = build_hammer_index(
            [_file("2026-09-13", [_product(sold=0, unsold=12, median=None,
                                           low=None, high=None, prices=[])])]
        )
        week = index[hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")][0]
        assert (week["sold"], week["unsold"]) == (0, 12)
        assert week["median"] is None

    def test_a_product_with_no_title_or_condition_is_dropped(self):
        index = build_hammer_index([_file("2026-09-13", [_product(title="", condition=None)])])
        assert index == {}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


class TestLoad:
    def test_unparseable_file_is_skipped_with_a_warning(self, tmp_path, caplog):
        (tmp_path / "2026-09-13_1.json").write_text("{not json")
        (tmp_path / "2026-09-06_2.json").write_text(
            json.dumps(_file("2026-09-06", [_product()], auction_id=2))
        )
        with caplog.at_level("WARNING"):
            files = load_hammer_files(tmp_path)
        assert [f["auction_id"] for f in files] == [2]
        assert "2026-09-13_1.json" in caplog.text

    def test_wrong_shaped_file_is_skipped_with_a_warning(self, tmp_path, caplog):
        (tmp_path / "notes.json").write_text(json.dumps({"hello": "world"}))
        with caplog.at_level("WARNING"):
            assert load_hammer_files(tmp_path) == []
        assert "notes.json" in caplog.text

    def test_missing_directory_is_a_warning_not_a_crash(self, tmp_path, caplog):
        with caplog.at_level("WARNING"):
            assert load_hammer_files(tmp_path / "nope") == []
        assert "not found" in caplog.text


# ---------------------------------------------------------------------------
# Attach
# ---------------------------------------------------------------------------


class TestAttach:
    def test_matched_lots_get_a_key_and_unmatched_lots_are_untouched(self):
        index = build_hammer_index([_file("2026-09-13", [_product()])])
        lots = [
            _merged("1"),
            _merged("2", title="SOMETHING ELSE"),
            _merged("3", condition="For Parts Only"),  # same title, other grade
        ]
        assert attach_hammer(lots, index) == 1
        assert lots[0]["hammer_key"] == hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")
        assert "hammer_key" not in lots[1]
        assert "hammer_key" not in lots[2]
        # The other grade of the same title still learns about the Excellent
        # history — under its own key, never as its own match.
        assert "hammer_alt_keys" not in lots[1]
        assert lots[2]["hammer_alt_keys"] == [hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")]
        assert "hammer_alt_keys" not in lots[0]

    def test_every_lot_of_a_repeat_product_shares_one_key(self):
        index = build_hammer_index([_file("2026-09-13", [_product()])])
        lots = [_merged(str(i)) for i in range(58)]
        assert attach_hammer(lots, index) == 58
        assert len({l["hammer_key"] for l in lots}) == 1

    def test_only_referenced_keys_are_shipped(self):
        index = build_hammer_index(
            [_file("2026-09-13", [_product(), _product(title="NEVER LISTED AGAIN")])]
        )
        lots = [_merged("1")]
        attach_hammer(lots, index)
        used = used_index(lots, index)
        assert list(used) == [hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")]
        assert used[list(used)[0]]["weeks"][0]["median"] == 14.0

    def test_alt_keys_are_ordered_nearest_grade_first_and_never_include_own(self):
        index = build_hammer_index(
            [
                _file(
                    "2026-09-13",
                    [
                        _product(condition="Brand New - Sealed"),
                        _product(condition="Excellent"),
                        _product(condition="Fair"),
                        _product(condition="Good"),
                    ],
                )
            ]
        )
        lot = _merged("1", condition="Good")
        attach_hammer([lot], index)
        assert lot["hammer_key"] == hammer_key("SHARK HD430C FLEXSTYLE", "Good")
        assert [k.rpartition("|")[2] for k in lot["hammer_alt_keys"]] == [
            "EXCELLENT",  # one step up
            "FAIR",  # two steps down (New With Defects sits between)
            "BRAND NEW - SEALED",
        ]

    def test_equidistant_grades_prefer_the_worse_one(self):
        # A borrowed figure should err low: Good borrows from New With Defects
        # (one step down) before Excellent (one step up).
        assert alt_key_order("GOOD", "NEW WITH DEFECTS") < alt_key_order("GOOD", "EXCELLENT")

    def test_a_blank_condition_history_is_never_offered_as_an_alternate(self):
        index = build_hammer_index(
            [_file("2026-09-13", [_product(condition=None), _product(condition="Good")])]
        )
        lot = _merged("1", condition="Excellent")
        attach_hammer([lot], index)
        assert lot["hammer_alt_keys"] == [hammer_key("SHARK HD430C FLEXSTYLE", "Good")]
        # ...but a lot that is itself ungraded still matches it exactly.
        blank = _merged("2", condition=None)
        attach_hammer([blank], index)
        assert blank["hammer_key"] == hammer_key("SHARK HD430C FLEXSTYLE", None)

    def test_alt_key_order_puts_unknown_grades_last_and_handles_no_condition(self):
        assert alt_key_order("GOOD", "USED") > alt_key_order("GOOD", "FOR PARTS ONLY")
        # A lot with no grade at all sees the ladder best-first.
        assert sorted(CONDITION_LADDER, key=lambda c: alt_key_order("", c)) == list(
            CONDITION_LADDER
        )

    def test_alt_keys_are_shipped_and_counted(self):
        index = build_hammer_index([_file("2026-09-13", [_product()])])
        lots = [_merged("1", condition="Good")]  # no Good history, Excellent exists
        assert attach_hammer(lots, index) == 0
        assert count_alt_only(lots) == 1
        assert list(used_index(lots, index)) == [
            hammer_key("SHARK HD430C FLEXSTYLE", "Excellent")
        ]

    def test_describe_reports_products_weeks_and_coverage(self):
        files = [_file("2026-09-13", [_product()])]
        index = build_hammer_index(files)
        assert describe(files, index, 1, 4, 1) == (
            "Hammer: 1 products across 1 week(s); 1/4 lots matched (25.0%), "
            "1 more (25.0%) only via another condition. "
            "Lots with neither show no sale history."
        )


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


class TestTransform:
    def test_hammer_key_survives_the_transform(self):
        item = _merged("1", hammer_key="SHARK|EXCELLENT")
        lot = Lot(**transform_item(item))
        assert lot.hammer_key == "SHARK|EXCELLENT"

    def test_a_lot_with_no_hammer_key_validates_with_none(self):
        lot = Lot(**transform_item(_merged("1")))
        assert lot.hammer_key is None
        assert lot.hammer_alt_keys is None

    def test_alt_keys_survive_the_transform_and_empty_becomes_none(self):
        lot = Lot(**transform_item(_merged("1", hammer_alt_keys=["SHARK|GOOD"])))
        assert lot.hammer_alt_keys == ["SHARK|GOOD"]
        lot = Lot(**transform_item(_merged("1", hammer_alt_keys=[])))
        assert lot.hammer_alt_keys is None


# ---------------------------------------------------------------------------
# End to end, through the build CLI
# ---------------------------------------------------------------------------


def _raw(lot_id, title, condition):
    return {
        "id": lot_id,
        "lot_number": str(lot_id),
        "title": title,
        "description": "",
        "description_raw": "",
        "thumb_url": "https://cdn.hibid.com/t",
        "image_url": "https://cdn.hibid.com/f",
        "lot_url": f"https://encoreauctions.hibid.com/lot/{lot_id}/?ref=catalog",
        "condition": condition,
        "close_at": "2026-09-20T13:00:00-04:00",
        "current_bid": 0.0,
        "status": "OPEN",
        "category_path": ["Tools", "Hand Tools"],
    }


def _cat(lot_id):
    return {
        "lot_number": str(lot_id),
        "title": "",
        "category": "Tools",
        "predicted_confidence": 0.8,
        "day": "Sunday",
        "is_bats_list": False,
        "bats_category": "",
        "bats_subcategory": "",
        "bats_buckets": [],
    }


def _run_build(tmp_path, monkeypatch, *extra_args):
    """Invoke the real CLI on a two-lot auction and return the bundle."""
    raw = [
        _raw(1, "SHARK HD430C FLEXSTYLE", "Excellent"),
        _raw(2, "A THING NOBODY HAS SOLD", "Good"),
    ]
    (tmp_path / "raw.json").write_text(json.dumps(raw))
    (tmp_path / "cat.json").write_text(json.dumps([_cat(1), _cat(2)]))
    out = tmp_path / "bundle.json"

    from build import __main__ as build_main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build",
            "--raw", str(tmp_path / "raw.json"),
            "--categorized", str(tmp_path / "cat.json"),
            "--output", str(out),
            *extra_args,
        ],
    )
    build_main.main()
    return json.loads(out.read_text())


class TestBundleShape:
    def test_without_the_flag_there_is_no_hammer_map_and_no_keys(
        self, tmp_path, monkeypatch
    ):
        bundle = _run_build(tmp_path, monkeypatch)
        assert "hammer" not in bundle
        assert all(lot["hammer_key"] is None for lot in bundle["lots"])

    def test_with_the_flag_every_referenced_key_resolves_in_the_map(
        self, tmp_path, monkeypatch
    ):
        hammer_dir = tmp_path / "hammer"
        hammer_dir.mkdir()
        (hammer_dir / "2026-09-13_774972.json").write_text(
            json.dumps(_file("2026-09-13", [_product()], auction_id=774972))
        )

        bundle = _run_build(tmp_path, monkeypatch, "--hammer", str(hammer_dir))

        assert "hammer" in bundle
        keys = [lot["hammer_key"] for lot in bundle["lots"]]
        assert keys == [hammer_key("SHARK HD430C FLEXSTYLE", "Excellent"), None]
        for lot in bundle["lots"]:
            for key in [lot["hammer_key"], *(lot["hammer_alt_keys"] or [])]:
                if key:
                    assert key in bundle["hammer"]
                    assert bundle["hammer"][key]["weeks"][0]["median"] == 14.0

    def test_an_empty_hammer_directory_builds_exactly_as_if_the_flag_were_absent(
        self, tmp_path, monkeypatch
    ):
        hammer_dir = tmp_path / "hammer"
        hammer_dir.mkdir()
        bundle = _run_build(tmp_path, monkeypatch, "--hammer", str(hammer_dir))
        assert "hammer" not in bundle
        assert all(lot["hammer_key"] is None for lot in bundle["lots"])
