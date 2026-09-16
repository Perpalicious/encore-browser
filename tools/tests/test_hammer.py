"""
Tests for `tools/hammer.py` — deriving hammer prices from a closed auction's
bid ladders and aggregating them per product.

Nothing here touches the network: the one test that exercises the pull mocks
`scraper.client.fetch_all_lots`. `bidHistory` (the authoritative per-lot
ladder) is never called at all — it costs one request per lot and carries real
bidder usernames.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hammer  # noqa: E402
from hammer import (  # noqa: E402
    HAMMER_LOT_QUERY,
    NoLots,
    NotClosed,
    aggregate,
    build_payload,
    check_closed,
    check_out_dir,
    derive_close_date,
    final_price,
    product_key,
    pull,
    summarise,
)

from scraper import client  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _lot(lead, *, bid_list, condition="EXCELLENT", status="CLOSED",
         close="9/13/2026 1:00:01 PM EST", lot_id=1):
    """A lotSearch result in the slim shape HAMMER_LOT_QUERY asks for."""
    return {
        "id": lot_id,
        "lotNumber": str(lot_id),
        "lead": lead,
        "description": condition,
        "bidList": bid_list,
        "lotState": {"status": status, "timeLeftTitle":
                     f"Internet Bidding closes at: {close}"},
    }


# ---------------------------------------------------------------------------
# Final price
# ---------------------------------------------------------------------------


class TestFinalPrice:
    def test_one_increment_below_the_head_of_the_ladder(self):
        # After close the ladder still starts at the next valid bid ABOVE the
        # final price, so the hammer is the head minus one increment.
        assert final_price([1450, 1475, 1500]) == 1425

    def test_zero_bid_lot_is_unsold_not_zero(self):
        # A lot nobody bid on opens its ladder at the opening bid, so the
        # formula yields 0. That is UNSOLD — never "$0".
        assert final_price([1.0, 2.0, 3.0]) is None

    def test_missing_or_short_ladder_is_unsold(self):
        assert final_price([]) is None
        assert final_price([5.0]) is None
        assert final_price(None) is None

    def test_non_uniform_ladder_still_uses_the_first_two_elements(self):
        # HiBid widens the increment further up the ladder; the bottom two
        # entries are the ones that bracket the last real bid.
        assert final_price([60, 65, 75, 100]) == 55

    def test_unparseable_entries_are_unsold(self):
        assert final_price(["a", "b"]) is None

    def test_floats_survive(self):
        assert final_price([12.5, 13.0]) == 12.0


# ---------------------------------------------------------------------------
# Product key
# ---------------------------------------------------------------------------


class TestProductKey:
    def test_key_is_title_and_condition_upper_cased(self):
        assert product_key(" shark hd430c ", "Excellent") == (
            "SHARK HD430C",
            "EXCELLENT",
        )

    def test_missing_condition_is_the_empty_string_not_a_crash(self):
        assert product_key("THING", None) == ("THING", "")

    def test_same_product_different_condition_is_a_different_key(self):
        assert product_key("X", "Excellent") != product_key("X", "For Parts Only")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


class TestAggregate:
    def test_median_low_high_are_over_sold_lots_only(self):
        products = aggregate(
            [
                _lot("WIDGET", bid_list=[11, 12], lot_id=1),   # 10
                _lot("WIDGET", bid_list=[21, 22], lot_id=2),   # 20
                _lot("WIDGET", bid_list=[31, 32], lot_id=3),   # 30
                _lot("WIDGET", bid_list=[1, 2], lot_id=4),     # unsold
            ]
        )
        assert len(products) == 1
        p = products[0]
        assert p["sold"] == 3
        assert p["unsold"] == 1
        assert p["median"] == 20
        assert p["low"] == 10
        assert p["high"] == 30
        assert p["prices"] == [10, 20, 30]

    def test_a_product_that_sold_nothing_is_still_emitted_with_nulls(self):
        # "listed 12×, sold 0" is information; dropping it would make an unsold
        # product indistinguishable from one that never ran.
        products = aggregate(
            [_lot("DUD", bid_list=[1, 2], lot_id=i) for i in range(12)]
        )
        assert len(products) == 1
        p = products[0]
        assert (p["sold"], p["unsold"]) == (0, 12)
        assert p["median"] is None and p["low"] is None and p["high"] is None
        assert p["prices"] == []

    def test_condition_splits_a_product(self):
        products = aggregate(
            [
                _lot("SHARK", bid_list=[21, 22], condition="EXCELLENT", lot_id=1),
                _lot("SHARK", bid_list=[6, 7], condition="FOR PARTS ONLY", lot_id=2),
            ]
        )
        assert [(p["condition"], p["median"]) for p in products] == [
            ("Excellent", 20.0),
            ("For Parts Only", 5.0),
        ]

    def test_title_casing_and_whitespace_do_not_split_a_product(self):
        products = aggregate(
            [
                _lot("Shark HD430C", bid_list=[11, 12], lot_id=1),
                _lot(" SHARK HD430C ", bid_list=[21, 22], lot_id=2),
            ]
        )
        assert len(products) == 1
        assert products[0]["sold"] == 2

    def test_output_is_ordered_deterministically(self):
        products = aggregate(
            [
                _lot("ZEBRA", bid_list=[11, 12], lot_id=1),
                _lot("APPLE", bid_list=[11, 12], lot_id=2),
            ]
        )
        assert [p["title"] for p in products] == ["APPLE", "ZEBRA"]


class TestCloseDate:
    def test_latest_close_across_lots_wins(self):
        results = [
            _lot("A", bid_list=[], close="9/13/2026 1:00:01 PM EST", lot_id=1),
            _lot("B", bid_list=[], close="9/14/2026 5:00:01 PM EST", lot_id=2),
        ]
        assert derive_close_date(results) == "2026-09-14"

    def test_unparseable_falls_back_to_today(self):
        from datetime import date

        results = [_lot("A", bid_list=[], close="not a date")]
        assert derive_close_date(results) == date.today().isoformat()


# ---------------------------------------------------------------------------
# Refusing a live auction
# ---------------------------------------------------------------------------


class TestClosedGate:
    def test_all_closed_passes(self):
        check_closed([_lot("A", bid_list=[], status="CLOSED")])

    def test_any_open_lot_raises(self):
        with pytest.raises(NotClosed) as exc:
            check_closed(
                [
                    _lot("A", bid_list=[], status="CLOSED", lot_id=1),
                    _lot("B", bid_list=[], status="OPEN", lot_id=2),
                ]
            )
        assert "OPEN: 1" in str(exc.value)

    def test_pull_refuses_a_live_auction_and_writes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            client,
            "fetch_all_lots",
            lambda auction_id, query=None: ("LIVE", [_lot("A", bid_list=[11, 12], status="OPEN")]),
        )
        with pytest.raises(NotClosed):
            pull(776904, tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_pull_refuses_an_empty_auction(self, tmp_path, monkeypatch):
        monkeypatch.setattr(client, "fetch_all_lots", lambda a, query=None: ("EMPTY", []))
        with pytest.raises(NoLots):
            pull(1, tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_pull_writes_one_aggregated_file_named_by_close_date(self, tmp_path, monkeypatch):
        results = [
            _lot("WIDGET", bid_list=[11, 12], lot_id=1),
            _lot("WIDGET", bid_list=[21, 22], lot_id=2),
            _lot("DUD", bid_list=[1, 2], lot_id=3),
        ]
        monkeypatch.setattr(
            client, "fetch_all_lots", lambda a, query=None: ("ENCORE TEST", results)
        )
        monkeypatch.setattr(hammer, "fetch_close_date", lambda a: None)
        path, payload = pull(774972, tmp_path)

        assert path.name == "2026-09-13_774972.json"
        assert json.loads(path.read_text()) == payload
        assert payload["auction_id"] == 774972
        assert payload["auction_name"] == "ENCORE TEST"
        assert payload["lots_seen"] == 3
        assert {p["title"] for p in payload["products"]} == {"WIDGET", "DUD"}
        # No temp file left behind by the atomic write.
        assert [p.name for p in tmp_path.iterdir()] == ["2026-09-13_774972.json"]

    def test_pull_prefers_the_auction_objects_close_date(self, tmp_path, monkeypatch):
        # HiBid blanks per-lot timeLeftTitle a few days after close (measured
        # 2026-09-16); the auction object's bidCloseDateTime must win, and must
        # win even when the lot strings disagree or are empty.
        results = [_lot("WIDGET", bid_list=[11, 12], close="")]
        monkeypatch.setattr(
            client, "fetch_all_lots", lambda a, query=None: ("X", results))
        monkeypatch.setattr(hammer, "fetch_close_date", lambda a: "2026-08-30")
        path, payload = pull(764524, tmp_path)
        assert payload["close_date"] == "2026-08-30"
        assert path.name == "2026-08-30_764524.json"

    def test_derive_close_date_order_of_preference(self):
        from datetime import date

        lots = [_lot("A", bid_list=[2, 3], close="9/14/2026 1:00:02 PM EST")]
        assert derive_close_date(lots, "2026-09-13") == "2026-09-13"   # auction wins
        assert derive_close_date(lots, None) == "2026-09-14"           # then lots
        assert derive_close_date([_lot("A", bid_list=[2, 3], close="")], None) \
            == date.today().isoformat()                                # then today

    def test_pull_asks_for_the_slim_query(self, tmp_path, monkeypatch):
        seen = {}

        def fake(auction_id, query=None):
            seen["query"] = query
            return ("X", [_lot("A", bid_list=[11, 12])])

        monkeypatch.setattr(client, "fetch_all_lots", fake)
        pull(1, tmp_path)
        assert seen["query"] == HAMMER_LOT_QUERY
        assert "bidList" in seen["query"]
        # bidHistory carries real usernames and costs a request per lot — it
        # must never appear in the weekly path.
        assert "bidHistory" not in seen["query"]


# ---------------------------------------------------------------------------
# The scraper's own query is untouched
# ---------------------------------------------------------------------------


class TestScraperQueryUnchanged:
    def test_default_lot_search_query_shape(self):
        # data/raw/auction_<ID>.json is defined by this document, and
        # scraper/__main__.py's first_seen carry-forward reads that file. The
        # hammer pull must not have changed it.
        q = client.LOT_SEARCH_QUERY
        assert q.startswith("query LotSearchLotOnly(")
        for field in (
            "featuredPicture { thumbnailLocation fullSizeLocation }",
            "pictures { fullSizeLocation }",
            "lotState { highBid status timeLeftTitle }",
            "category { categoryName fullCategory }",
        ):
            assert field in q
        assert "bidList" not in q

    def test_default_payload_is_unchanged(self):
        assert client._build_payload(741675, 2, 500) == {
            "operationName": "LotSearchLotOnly",
            "variables": {
                "auctionId": 741675,
                "pageNumber": 2,
                "pageLength": 500,
            },
            "query": client.LOT_SEARCH_QUERY,
        }

    def test_a_custom_query_carries_its_own_operation_name(self):
        payload = client._build_payload(1, 1, 500, HAMMER_LOT_QUERY)
        assert payload["operationName"] == "LotSearchHammer"
        assert payload["query"] == HAMMER_LOT_QUERY
        assert payload["variables"] == {
            "auctionId": 1,
            "pageNumber": 1,
            "pageLength": 500,
        }

    def test_hammer_query_keeps_the_pagination_contract(self):
        for token in ("pagedResults", "totalCount", "$pageNumber", "$pageLength"):
            assert token in HAMMER_LOT_QUERY


# ---------------------------------------------------------------------------
# Output guards
# ---------------------------------------------------------------------------


class TestOutputGuards:
    @pytest.mark.parametrize("bad", ["data/raw", "data/categorized", "data/raw/nested"])
    def test_refuses_to_write_where_the_build_reads(self, bad):
        with pytest.raises(SystemExit):
            check_out_dir(Path(bad))

    def test_allows_the_default_directory(self, tmp_path):
        check_out_dir(Path("data/hammer"))
        check_out_dir(tmp_path)

    def test_summary_names_the_file_and_the_counts(self, tmp_path):
        payload = build_payload(
            774972, "ENCORE", [_lot("WIDGET", bid_list=[11, 12], lot_id=1)]
        )
        text = summarise(payload, tmp_path / "x.json")
        assert "1 distinct products; 1 sold, 0 unsold" in text
        assert "x.json" in text
