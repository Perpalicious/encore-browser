"""
Tests for scraper/condition.py — condition extraction and description parsing.
"""

import pytest
from scraper.condition import CONDITION_LABELS, parse_condition


class TestConditionPassthrough:
    """HiBid's condition string is stored 1:1, title-cased."""

    @pytest.mark.parametrize(
        "raw_value, expected",
        [
            # HiBid's full observed vocabulary (30,358 lots, week of 2026-08-16)
            ("BRAND NEW - SEALED", "Brand New - Sealed"),
            ("BRAND NEW - OPEN BOX", "Brand New - Open Box"),
            ("NEW (ADJUSTED QUANTITY)", "New (Adjusted Quantity)"),
            ("BEST BEFORE (GROCERY)", "Best Before (Grocery)"),
            ("EXCELLENT", "Excellent"),
            ("GOOD", "Good"),
            ("NEW WITH DEFECTS", "New With Defects"),
            ("FAIR", "Fair"),
            ("HEAVILY USED", "Heavily Used"),
            ("FOR PARTS ONLY", "For Parts Only"),
            ("DO NOT BID", "Do Not Bid"),
            # HiBid is inconsistent about case on a handful of lots
            ("Excellent", "Excellent"),
            ("brand new - sealed", "Brand New - Sealed"),
            # Stray whitespace around the value
            ("  GOOD  ", "Good"),
        ],
    )
    def test_condition_values(self, raw_value: str, expected: str) -> None:
        description = f"Condition: {raw_value}\nSome free-form text here."
        condition, _, _ = parse_condition(description)
        assert condition == expected, (
            f"Condition: '{raw_value}' should store as '{expected}', got '{condition}'"
        )

    def test_every_known_label_round_trips(self) -> None:
        """CONDITION_LABELS must all survive parsing unchanged — it drives the
        viewer's chip order and colour map, so a typo there is silent."""
        for label in CONDITION_LABELS:
            condition, _, _ = parse_condition(f"Condition: {label.upper()}\ntext")
            assert condition == label

    def test_unknown_condition_passes_through(self) -> None:
        """A value HiBid adds later must reach the viewer, not become null."""
        description = "Condition: REFURBISHED\nSome text."
        condition, _, _ = parse_condition(description)
        assert condition == "Refurbished"

    def test_placeholder_returns_none(self) -> None:
        """'Select Condition Here' is an unfilled dropdown, not a grading."""
        description = "Condition: Select Condition Here\nSome text."
        condition, _, _ = parse_condition(description)
        assert condition is None

    def test_no_condition_line_returns_none(self) -> None:
        description = "Some free-form text with no condition line."
        condition, _, _ = parse_condition(description)
        assert condition is None

    def test_empty_string_returns_none(self) -> None:
        condition, price, remaining = parse_condition("")
        assert condition is None
        assert price is None
        assert remaining == ""

    def test_none_input_returns_none(self) -> None:
        condition, price, remaining = parse_condition(None)
        assert condition is None
        assert price is None
        assert remaining == ""


class TestEstRetailPrice:
    """Test Est. Retail Price extraction."""

    def test_basic_price(self) -> None:
        description = "Est. Retail Price: 55.00\nCondition: NEW\nSome text."
        _, price, _ = parse_condition(description)
        assert price == 55.00

    def test_price_with_dollar_sign(self) -> None:
        description = "Est. Retail Price: $249.99\nSome text."
        _, price, _ = parse_condition(description)
        assert price == 249.99

    def test_price_with_comma(self) -> None:
        description = "Est. Retail Price: 1,299.00\nSome text."
        _, price, _ = parse_condition(description)
        assert price == 1299.00

    def test_no_price_returns_none(self) -> None:
        description = "Condition: NEW\nSome text."
        _, price, _ = parse_condition(description)
        assert price is None

    def test_integer_price(self) -> None:
        description = "Est. Retail Price: 100\nSome text."
        _, price, _ = parse_condition(description)
        assert price == 100.0


class TestDescriptionRemaining:
    """Test that structured Key: Value lines are stripped from description."""

    def test_strips_structured_lines(self) -> None:
        description = (
            "Est. Retail Price: 55.00\n"
            "Condition: BRAND NEW - SEALED\n"
            "In packaging? Yes\n"
            "Requires Assembly? No\n"
            "Is Item Functional? Yes\n"
            "Missing Major Parts? No\n"
            "Is Item Damaged? No\n"
            "\n"
            "This is the free-form description text."
        )
        _, _, remaining = parse_condition(description)
        assert "free-form description text" in remaining
        assert "Est. Retail Price" not in remaining
        assert "Condition:" not in remaining
        assert "In packaging?" not in remaining

    def test_preserves_freeform_text(self) -> None:
        description = (
            "Condition: NEW\n"
            "Apple iPhone 15 Pro Max 256GB Natural Titanium, unlocked.\n"
            "Some additional details here."
        )
        _, _, remaining = parse_condition(description)
        assert "Apple iPhone" in remaining
        assert "additional details" in remaining

    def test_empty_after_stripping(self) -> None:
        description = (
            "Condition: NEW\n"
            "In packaging? Yes\n"
            "Requires Assembly? No\n"
        )
        _, _, remaining = parse_condition(description)
        assert remaining == ""

    def test_description_with_no_structured_lines(self) -> None:
        description = "This is a plain description with no structured lines."
        _, _, remaining = parse_condition(description)
        assert remaining == description


class TestFullDescription:
    """Integration-style tests with realistic HiBid descriptions."""

    def test_full_hibid_description(self) -> None:
        description = (
            "Est. Retail Price: 249.00\n"
            "Condition: BRAND NEW - SEALED\n"
            "In packaging? Yes\n"
            "Requires Assembly? No\n"
            "Is Item Functional? Yes\n"
            "Missing Major Parts? No\n"
            "Is Item Damaged? No\n"
            "\n"
            "Apple AirPods Pro (2nd generation) with MagSafe Charging Case."
        )
        condition, price, remaining = parse_condition(description)
        assert condition == "Brand New - Sealed"
        assert price == 249.00
        assert "Apple AirPods Pro" in remaining
        assert "Condition:" not in remaining
        assert "Est. Retail Price" not in remaining
