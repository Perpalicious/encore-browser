"""
Tests for scraper/parser.py — HiBid lot response → output JSON mapping.
Includes the mandatory redaction test (verification gate requirement).
"""

import json
import os
import pathlib
import re

import pytest
from scraper.parser import map_lot

# ---------------------------------------------------------------------------
# Load fixture
# ---------------------------------------------------------------------------

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample_lot_search.json"


@pytest.fixture(scope="module")
def fixture_data():
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def fixture_results(fixture_data):
    return fixture_data["data"]["lotSearch"]["results"]


@pytest.fixture(scope="module")
def mapped_lots(fixture_results):
    return [map_lot(item) for item in fixture_results]


# ---------------------------------------------------------------------------
# Basic field presence
# ---------------------------------------------------------------------------


class TestFieldPresence:
    def test_all_required_fields_present(self, mapped_lots):
        required = [
            "id",
            "lot_number",
            "title",
            "description_raw",
            "description",
            "condition",
            "est_retail_price",
            "thumb_url",
            "image_url",
            "additional_images",
            "current_bid",
            "status",
            "category_path",
            "hibid_category_leaf",
            "hibid_category_path",
            "close_at",
            "lot_url",
        ]
        for lot in mapped_lots:
            for field in required:
                assert field in lot, f"Field '{field}' missing in lot {lot.get('id')}"

    def test_additional_images_is_list(self, mapped_lots):
        for lot in mapped_lots:
            assert isinstance(lot["additional_images"], list), (
                f"additional_images should be list for lot {lot.get('id')}"
            )


# ---------------------------------------------------------------------------
# Field mapping correctness
# ---------------------------------------------------------------------------


class TestFieldMapping:
    def test_id_mapping(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            assert mapped["id"] == raw["id"]

    def test_lot_number_mapping(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            assert mapped["lot_number"] == raw["lotNumber"]

    def test_title_from_lead(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            assert mapped["title"] == raw["lead"]

    def test_description_raw_preserved(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            assert mapped["description_raw"] == raw["description"]

    def test_thumb_url_from_featured_picture(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            fp = raw.get("featuredPicture") or {}
            expected = fp.get("thumbnailLocation") or ""
            assert mapped["thumb_url"] == expected

    def test_image_url_from_featured_picture(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            fp = raw.get("featuredPicture") or {}
            expected = fp.get("fullSizeLocation") or ""
            assert mapped["image_url"] == expected

    def test_current_bid_from_lot_state(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            ls = raw.get("lotState") or {}
            raw_bid = ls.get("highBid")
            if raw_bid is None:
                assert mapped["current_bid"] is None
            else:
                assert mapped["current_bid"] == float(raw_bid)

    def test_status_from_lot_state(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            ls = raw.get("lotState") or {}
            assert mapped["status"] == (ls.get("status") or "")

    def test_category_leaf_and_path(self, fixture_results, mapped_lots):
        for raw, mapped in zip(fixture_results, mapped_lots):
            cats = raw.get("category") or []
            if cats:
                assert mapped["hibid_category_leaf"] == cats[0].get("categoryName", "")
                assert mapped["hibid_category_path"] == cats[0].get("fullCategory", "")
            else:
                assert mapped["hibid_category_leaf"] == ""
                assert mapped["hibid_category_path"] == ""

    def test_category_path_is_root_to_leaf(self, mapped_lots):
        """HiBid sends category leaf → root; output category_path must be root → leaf."""
        # Lot 100001's fixture category is [Headphones(leaf), Audio, Electronics(root)].
        lot = next(l for l in mapped_lots if l["id"] == 100001)
        assert lot["category_path"] == ["Electronics", "Audio", "Headphones"]

    def test_category_path_single_level(self, mapped_lots):
        """A single-element category array yields a one-element path."""
        lot = next(l for l in mapped_lots if l["id"] == 100002)
        # Fixture lot 100002 has one category entry: Stand Mixers
        assert lot["category_path"] == ["Stand Mixers"]

    def test_category_path_always_list(self, mapped_lots):
        for lot in mapped_lots:
            assert isinstance(lot["category_path"], list)
            assert all(isinstance(c, str) for c in lot["category_path"])


# ---------------------------------------------------------------------------
# Lot URL
# ---------------------------------------------------------------------------


class TestLotUrl:
    LOT_URL_RE = re.compile(
        r"^https://encoreauctions\.hibid\.com/lot/\d+/.*"
    )

    def test_lot_url_format(self, mapped_lots):
        for lot in mapped_lots:
            assert self.LOT_URL_RE.match(lot["lot_url"]), (
                f"lot_url '{lot['lot_url']}' does not match expected pattern"
            )

    def test_lot_url_contains_id(self, mapped_lots):
        for lot in mapped_lots:
            assert str(lot["id"]) in lot["lot_url"]


# ---------------------------------------------------------------------------
# Condition parsing through map_lot
# ---------------------------------------------------------------------------


class TestConditionInMappedLot:
    def test_brand_new_sealed(self, mapped_lots):
        lot = next(l for l in mapped_lots if l["id"] == 100001)
        assert lot["condition"] == "Brand New - Sealed"
        assert lot["est_retail_price"] == 249.00

    def test_brand_new_open_box(self, mapped_lots):
        lot = next(l for l in mapped_lots if l["id"] == 100002)
        assert lot["condition"] == "Brand New - Open Box"
        assert lot["est_retail_price"] == 499.99

    def test_good(self, mapped_lots):
        lot = next(l for l in mapped_lots if l["id"] == 100003)
        assert lot["condition"] == "Good"

    def test_heavily_used(self, mapped_lots):
        lot = next(l for l in mapped_lots if l["id"] == 100004)
        assert lot["condition"] == "Heavily Used"

    def test_no_condition_returns_none(self, mapped_lots):
        lot = next(l for l in mapped_lots if l["id"] == 100005)
        assert lot["condition"] is None


# ---------------------------------------------------------------------------
# close_at parsing
# ---------------------------------------------------------------------------


class TestCloseAt:
    def test_mislabelled_est_in_summer_resolves_to_edt(self, mapped_lots):
        # "5/24/2026 12:00:00 PM EST" — HiBid hardcodes "EST" year-round, but
        # 24 May is daylight time. The label is ignored; the date decides.
        lot = next(l for l in mapped_lots if l["id"] == 100001)
        assert lot["close_at"] is not None
        assert "-04:00" in lot["close_at"]

    def test_edt_timezone_parsed(self, mapped_lots):
        lot = next(l for l in mapped_lots if l["id"] == 100003)
        # "5/25/2026 12:00:00 PM EDT" → should include -04:00
        assert lot["close_at"] is not None
        assert "-04:00" in lot["close_at"]

    def test_winter_date_resolves_to_est(self):
        # Standard time really is -05:00, and must stay that way.
        from scraper.parser import _parse_close_at
        got = _parse_close_at("Internet Bidding closes at: 1/11/2026 1:00:00 PM EST")
        assert got == "2026-01-11T13:00:00-05:00"

    def test_wall_clock_is_preserved_verbatim(self):
        # The number HiBid prints is what the site shows; only the offset is
        # ours to decide. Regression guard for the hour-shift bug.
        from scraper.parser import _parse_close_at
        got = _parse_close_at("Internet Bidding closes at: 8/16/2026 1:00:01 PM EST")
        assert got == "2026-08-16T13:00:01-04:00"

    def test_close_at_is_iso_format(self, mapped_lots):
        import datetime
        for lot in mapped_lots:
            if lot["close_at"] is not None:
                # Should parse as an ISO 8601 datetime
                try:
                    datetime.datetime.fromisoformat(lot["close_at"])
                except ValueError:
                    pytest.fail(
                        f"close_at '{lot['close_at']}' for lot {lot['id']} "
                        "is not valid ISO 8601"
                    )


# ---------------------------------------------------------------------------
# Additional images
# ---------------------------------------------------------------------------


class TestAdditionalImages:
    def test_additional_images_excludes_featured(self, mapped_lots):
        """additional_images must not duplicate the image_url."""
        for lot in mapped_lots:
            if lot["image_url"]:
                assert lot["image_url"] not in lot["additional_images"], (
                    f"image_url appears in additional_images for lot {lot['id']}"
                )

    def test_lot_with_multiple_pictures(self, mapped_lots):
        lot = next(l for l in mapped_lots if l["id"] == 100003)
        # Fixture has 3 pictures; 1 is featured → 2 additional
        assert len(lot["additional_images"]) == 2


# ---------------------------------------------------------------------------
# Redaction test (verification gate)
# ---------------------------------------------------------------------------


class TestTokenRedaction:
    """
    Verify that the token value never appears in error messages.
    This simulates an exception while HIBID_TOKEN is set and checks that the
    token is not leaked in the error string.
    """

    def test_token_not_leaked_in_error(self, monkeypatch):
        fake_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.FAKE_PAYLOAD.FAKE_SIGNATURE"
        monkeypatch.setenv("HIBID_TOKEN", fake_token)

        # Import client here to get access to _redact_token
        from scraper.client import _redact_token

        # Simulate an error message that accidentally embeds the token
        dangerous_message = f"Request failed: Authorization: Bearer {fake_token}"
        safe_message = _redact_token(fake_token, dangerous_message)

        assert fake_token not in safe_message, (
            "Token value was found in the error message — redaction failed!"
        )
        assert "<HIBID_TOKEN redacted>" in safe_message

    def test_short_token_not_redacted(self):
        """Tokens shorter than 8 chars are not secrets — no redaction expected."""
        from scraper.client import _redact_token
        short = "abc123"
        msg = f"Error with {short}"
        result = _redact_token(short, msg)
        # Short values aren't redacted (avoid false positives in log messages)
        assert short in result

    def test_none_token_safe(self):
        """_redact_token with None token should return message unchanged."""
        from scraper.client import _redact_token
        msg = "Some error message"
        result = _redact_token(None, msg)
        assert result == msg
