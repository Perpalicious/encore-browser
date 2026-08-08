"""
`close_at` and `bat_subtype` passthrough.

Both fields were already available upstream and thrown away here: the scraper
has parsed `close_at` since the beginning (scraper/parser.py) and merge.py
carries it into the transform input, but the Lot shape never emitted it, so no
bundle has ever contained a closing time. `bat_subtype` is the new free-form
level under the fixed Bat's List buckets.
"""

from __future__ import annotations

from build.schema import Lot
from build.transform import transform_item


SHAPE_A = {
    "lot_number": "S-1042",
    "title": "Scrub Brush 3-Pack",
    "description": "",
    "lot_url": "https://encoreauctions.hibid.com/lot/1042/?ref=catalog",
    "category": "Cleaning",
    "subcategory": "Brushes",
    "confidence": "low",
    "is_bats_list": True,
    "bats_buckets": ["Cleaning supplies & tools"],
    "close_at": "2026-08-09T13:04:00-04:00",
    "bats_subtype": "scrub brushes",
}

# Shape B is detected purely by the presence of `bats_category`.
SHAPE_B = {
    "lot_number": "M-2042",
    "title": "Lysol Disinfectant",
    "description": "",
    "lot_url": "https://encoreauctions.hibid.com/lot/2042/?ref=catalog",
    "hibid_category_path": "Home > Cleaning",
    "is_bats_list": True,
    "bats_category": "Cleaning supplies & tools",
    "bats_subcategory": "",
    "close_at": "2026-08-10T13:04:00-04:00",
    "bats_subtype": "Detergents",
}


class TestCloseAt:
    def test_shape_a_keeps_the_closing_time(self):
        assert transform_item(SHAPE_A)["close_at"] == "2026-08-09T13:04:00-04:00"

    def test_shape_b_keeps_the_closing_time(self):
        assert transform_item(SHAPE_B)["close_at"] == "2026-08-10T13:04:00-04:00"

    def test_absent_is_none_not_empty_string(self):
        # The viewer feature-detects on `close_at` being truthy, so an older
        # bundle must read as "no time", never as an unparseable one.
        item = {**SHAPE_A}
        del item["close_at"]
        assert transform_item(item)["close_at"] is None
        assert Lot(**transform_item(item)).close_at is None

    def test_empty_string_is_none(self):
        assert transform_item({**SHAPE_A, "close_at": ""})["close_at"] is None

    def test_still_derives_the_day_from_it(self):
        # The one thing close_at was already used for must keep working.
        assert transform_item(SHAPE_A)["day"] == "Sunday"
        assert transform_item(SHAPE_B)["day"] == "Monday"


class TestBatSubtype:
    def test_shape_a_passthrough(self):
        assert transform_item(SHAPE_A)["bat_subtype"] == "scrub brushes"

    def test_shape_b_passthrough(self):
        assert transform_item(SHAPE_B)["bat_subtype"] == "detergents"

    def test_normalised_so_near_duplicates_collapse(self):
        # One drill-down node, not three.
        variants = ["Scrub Brushes", "scrub  brushes", "  scrub brushes\n"]
        assert {transform_item({**SHAPE_A, "bats_subtype": v})["bat_subtype"] for v in variants} == {
            "scrub brushes"
        }

    def test_absent_blank_and_non_string_are_none(self):
        for value in ("", "   ", None, 42, ["scrub brushes"]):
            assert transform_item({**SHAPE_A, "bats_subtype": value})["bat_subtype"] is None
        item = {**SHAPE_A}
        del item["bats_subtype"]
        assert transform_item(item)["bat_subtype"] is None

    def test_validates_on_the_lot_schema(self):
        lot = Lot(**transform_item(SHAPE_A))
        assert lot.bat_subtype == "scrub brushes"
        assert lot.close_at == "2026-08-09T13:04:00-04:00"
