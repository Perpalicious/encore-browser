"""
Tests for build/merge.py — joining raw scrape items to the Auction Agent's
categorized output. Covers:
  - happy path with join on raw.id == categorized.lot_number (observed shape)
  - alternate join on raw.lot_number == categorized.lot_number
  - unmatched categorized items raise MergeError
  - empty raw with non-empty categorized raises
  - raw scraper fields (title, image_url, etc.) survive the join
  - enrichment fields (category, is_bats_list, ...) are layered on top
  - empty agent fields don't overwrite real raw fields
"""

from __future__ import annotations

import pytest

from build.merge import merge, MergeError, report_overlap


def _raw_item(**overrides):
    base = {
        "id": 100001,
        "lot_number": "1",
        "title": "REAL TITLE FROM SCRAPER",
        "description": "real description",
        "description_raw": "real description raw",
        "thumb_url": "https://cdn.hibid.com/thumb/100001",
        "image_url": "https://cdn.hibid.com/full/100001",
        "lot_url": "https://encoreauctions.hibid.com/lot/100001/?ref=catalog",
        "condition": "New",
        "close_at": "2026-05-24T12:00:00-04:00",
        "current_bid": 5.0,
        "status": "OPEN",
        # HiBid native category tree, root → leaf
        "category_path": ["Home Goods & Decor", "Home Goods", "Bed / Bath Items"],
    }
    base.update(overrides)
    return base


def _cat_item(**overrides):
    """Categorized item in the shape observed from the Auction Agent."""
    base = {
        "lot_number": "100001",  # NOTE: this is actually the HiBid id (string)
        "title": "",             # agent typically blanks these
        "url": "",
        "image_url": "",
        "auction_id": "741675",
        "auction_name": "Test",
        "category": "Electronics",
        "category_source": "rules",
        "predicted_confidence": 0.8,
        "day": "Sunday",
        "is_bats_list": True,
        "bats_category": "Smart Home",
        "bats_subcategory": "Smart lights",
        "is_nice_pick": False,
        "nice_pick_category": "",
        "nice_pick_subcategory": "",
    }
    base.update(overrides)
    return base


class TestHappyPathJoinById:
    def test_match_by_id_as_string(self):
        raw = [_raw_item()]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat)
        assert len(merged) == 1
        assert merged[0]["title"] == "REAL TITLE FROM SCRAPER"
        assert merged[0]["image_url"] == "https://cdn.hibid.com/full/100001"
        # Categories come from the raw scrape's native tree, NOT the agent.
        assert merged[0]["category_path"] == [
            "Home Goods & Decor", "Home Goods", "Bed / Bath Items"
        ]
        assert merged[0]["is_bats_list"] is True

    def test_three_items_all_match(self):
        raw = [_raw_item(id=i, lot_number=str(i - 99999), title=f"item {i}") for i in (100001, 100002, 100003)]
        cat = [_cat_item(lot_number=str(i)) for i in (100001, 100002, 100003)]
        merged = merge(raw, cat)
        assert [m["title"] for m in merged] == ["item 100001", "item 100002", "item 100003"]


class TestHappyPathJoinByLotNumber:
    def test_match_by_display_lot_number(self):
        raw = [_raw_item(id=100001, lot_number="42")]
        cat = [_cat_item(lot_number="42")]  # agent uses display lot number
        merged = merge(raw, cat)
        assert len(merged) == 1
        assert merged[0]["lot_number"] == "42"
        assert merged[0]["title"] == "REAL TITLE FROM SCRAPER"


class TestUnmatchedItems:
    def test_single_unmatched_raises(self):
        raw = [_raw_item(id=100001, lot_number="1")]
        cat = [_cat_item(lot_number="999999")]
        with pytest.raises(MergeError) as exc:
            merge(raw, cat)
        assert "999999" in str(exc.value)
        assert "1 of 1" in str(exc.value)

    def test_partial_unmatched_raises(self):
        raw = [_raw_item(id=100001, lot_number="1")]
        cat = [_cat_item(lot_number="100001"), _cat_item(lot_number="ZZZ_BAD")]
        with pytest.raises(MergeError) as exc:
            merge(raw, cat)
        assert "ZZZ_BAD" in str(exc.value)
        assert "1 of 2" in str(exc.value)

    def test_empty_raw_with_non_empty_categorized_raises(self):
        with pytest.raises(MergeError):
            merge([], [_cat_item()])

    def test_error_message_suggests_drop_orphans(self):
        raw = [_raw_item(id=100001)]
        cat = [_cat_item(lot_number="999999")]
        with pytest.raises(MergeError) as exc:
            merge(raw, cat)
        assert "--drop-orphans" in str(exc.value)


class TestDropOrphans:
    def test_drop_orphans_keeps_matched_drops_unmatched(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="build.merge")
        raw = [_raw_item(id=100001, title="real one")]
        cat = [
            _cat_item(lot_number="100001"),                  # matches
            _cat_item(lot_number="ORPHAN_A", category="X"),
            _cat_item(lot_number="ORPHAN_B"),
        ]
        merged = merge(raw, cat, drop_orphans=True)
        assert len(merged) == 1
        assert merged[0]["title"] == "real one"
        # Each orphan logged with its lot_number
        warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("ORPHAN_A" in m for m in warnings)
        assert any("ORPHAN_B" in m for m in warnings)
        # Summary line present
        assert any("Dropped 2 orphan items" in m for m in warnings)

    def test_drop_orphans_no_orphans_no_warnings(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="build.merge")
        raw = [_raw_item(id=100001)]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat, drop_orphans=True)
        assert len(merged) == 1
        assert caplog.records == []

    def test_drop_orphans_all_orphan_returns_empty(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="build.merge")
        raw = []
        cat = [_cat_item(lot_number="X")]
        merged = merge(raw, cat, drop_orphans=True)
        assert merged == []
        assert any("Dropped 1 orphan items" in r.getMessage() for r in caplog.records)

    def test_drop_orphans_logs_enrichment_fields(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="build.merge")
        raw = []
        cat = [_cat_item(
            lot_number="X",
            category="Electronics",
            bats_category="Smart Home",
            is_bats_list=True,
        )]
        merge(raw, cat, drop_orphans=True)
        record_msg = next(
            r.getMessage() for r in caplog.records if "lot_number='X'" in r.getMessage()
        )
        assert "Electronics" in record_msg
        assert "Smart Home" in record_msg


class TestFieldPrecedence:
    def test_raw_fields_win_over_blank_agent_fields(self):
        raw = [_raw_item(title="REAL TITLE", image_url="https://cdn.real")]
        cat = [_cat_item(title="", image_url="")]
        merged = merge(raw, cat)
        assert merged[0]["title"] == "REAL TITLE"
        assert merged[0]["image_url"] == "https://cdn.real"

    def test_bat_enrichment_layered_on_but_agent_category_dropped(self):
        raw = [_raw_item()]
        cat = [_cat_item(category="Toys & Kids", subcategory="Action Figures",
                         is_bats_list=True,
                         bats_category="Bucket A", bats_subcategory="Bucket B")]
        merged = merge(raw, cat)
        # Bat flags survive from the agent...
        assert merged[0]["bats_category"] == "Bucket A"
        assert merged[0]["bats_subcategory"] == "Bucket B"
        assert merged[0]["is_bats_list"] is True
        # ...but the agent's category/subcategory are dropped entirely.
        assert "category" not in merged[0] or merged[0].get("category") != "Toys & Kids"
        assert merged[0].get("subcategory") != "Action Figures"
        # category_path is the raw scrape's native tree.
        assert merged[0]["category_path"] == [
            "Home Goods & Decor", "Home Goods", "Bed / Bath Items"
        ]

    def test_agent_category_path_ignored_raw_wins(self):
        """Even if the agent (wrongly) supplies a category_path, raw's wins."""
        raw = [_raw_item(category_path=["RawRoot", "RawLeaf"])]
        cat = [_cat_item(category_path=["AgentRoot", "AgentLeaf"])]
        merged = merge(raw, cat)
        assert merged[0]["category_path"] == ["RawRoot", "RawLeaf"]


class TestCategoryPathFromHibidString:
    """Older scrapes emit hibid_category_path as a ' - ' delimited string with
    no discrete category_path array. The build must parse it into a path."""

    def _raw_str(self, **kw):
        # A raw item WITHOUT category_path array, only the hibid string fields.
        base = dict(_raw_item())
        base.pop("category_path", None)
        base.update(kw)
        return base

    def test_parses_hibid_category_path_string(self):
        raw = [self._raw_str(
            hibid_category_path="Antiques & Collectibles - Collectibles - Advertising",
            hibid_category_leaf="Advertising",
        )]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat)
        assert merged[0]["category_path"] == [
            "Antiques & Collectibles", "Collectibles", "Advertising"
        ]

    def test_multiword_names_not_oversplit(self):
        """' - ' (space-hyphen-space) is the delimiter; names with '&', '/',
        or a bare '-' must stay intact."""
        raw = [self._raw_str(
            hibid_category_path="Home Goods & Decor - Kitchen / Dining - Knives - Blocks",
            hibid_category_leaf="Knives - Blocks",
        )]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat)
        # "Home Goods & Decor" and "Kitchen / Dining" stay whole; the bare
        # hyphen inside "Knives - Blocks" IS a delimiter here (it's surrounded
        # by spaces), so it splits — that's correct per the " - " rule.
        assert merged[0]["category_path"] == [
            "Home Goods & Decor", "Kitchen / Dining", "Knives", "Blocks"
        ]

    def test_single_level_string(self):
        raw = [self._raw_str(hibid_category_path="Electronics", hibid_category_leaf="Electronics")]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat)
        assert merged[0]["category_path"] == ["Electronics"]

    def test_missing_hibid_path_yields_empty(self):
        raw = [self._raw_str(hibid_category_path="", hibid_category_leaf="")]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat)
        assert merged[0]["category_path"] == []

    def test_discrete_array_preferred_over_string(self):
        """If both shapes are present, the discrete array wins (newer scrapes)."""
        raw = [_raw_item(
            category_path=["Array Root", "Array Leaf"],
            hibid_category_path="String Root - String Leaf",
        )]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat)
        assert merged[0]["category_path"] == ["Array Root", "Array Leaf"]


class TestCategoryPathDrivesCategoryAndSub:
    """Through the full transform, category=root and subcategory=leaf."""

    def test_root_and_leaf_from_hibid_string(self):
        from build.transform import transform_all
        raw = [{
            "id": 100001, "lot_number": "1", "title": "X",
            "description": "", "image_url": "i", "thumb_url": "t",
            "lot_url": "https://encoreauctions.hibid.com/lot/100001/x",
            "hibid_category_path": "Antiques & Collectibles - Collectibles - Advertising",
            "hibid_category_leaf": "Advertising",
        }]
        cat = [_cat_item(lot_number="100001")]
        merged = merge(raw, cat)
        lots = transform_all(merged)
        assert lots[0].category_path == ["Antiques & Collectibles", "Collectibles", "Advertising"]
        assert lots[0].category == "Antiques & Collectibles"   # root
        assert lots[0].subcategory == "Advertising"             # leaf

    def test_raw_condition_preserved_when_agent_omits(self):
        raw = [_raw_item(condition="Like New")]
        cat = [_cat_item()]  # no condition in agent output
        merged = merge(raw, cat)
        assert merged[0]["condition"] == "Like New"

    def test_raw_description_wins_over_non_empty_agent_description(self):
        """When raw has meaningful description text, agent's value never overwrites."""
        raw = [_raw_item(description="Premium leather wallet, gently used.")]
        cat = [_cat_item(description="ACME PREMIUM WALLET")]  # agent often just duplicates title
        merged = merge(raw, cat)
        assert merged[0]["description"] == "Premium leather wallet, gently used."

    def test_agent_description_fills_in_when_raw_empty(self):
        """If raw description is empty (all-structured), agent value fills it."""
        raw = [_raw_item(description="", description_raw="Condition: Brand New")]
        cat = [_cat_item(description="ACME WIDGET")]
        merged = merge(raw, cat)
        assert merged[0]["description"] == "ACME WIDGET"


class TestReportOverlap:
    def test_overlap_string_lists_match_counts(self):
        raw = [_raw_item(id=1, lot_number="1"),
               _raw_item(id=2, lot_number="2"),
               _raw_item(id=3, lot_number="3")]
        cat = [_cat_item(lot_number="1"),
               _cat_item(lot_number="2"),
               _cat_item(lot_number="99")]
        s = report_overlap(raw, cat)
        assert "raw items: 3" in s
        assert "categorized items: 3" in s
        assert "unmatched: 1" in s


class TestDayDerivation:
    def test_day_derived_from_close_at_when_missing(self):
        raw = [_raw_item(close_at="2026-05-24T12:00:00-05:00")]  # Sunday
        cat = [_cat_item()]
        # Strip day from cat so derivation triggers
        del cat[0]["day"]
        merged = merge(raw, cat)
        assert merged[0]["day"] == "Sunday"
