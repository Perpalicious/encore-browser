"""
Tests for `tools/prefilter.py` — the per-bucket candidate shortlist.

Fixtures are inline on purpose. `data/` is gitignored and holds only the
current week, so a test that read it would pass on the machine that wrote it
and fail everywhere else.

The named titles below are real lots from the 2026-08-15 run that the
un-prefiltered flagging pass got wrong. They are the regression surface: if a
seed edit ever stops shortlisting them, that run regressed to the behaviour
this whole tool exists to fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prefilter import (  # noqa: E402
    BASE_ROW,
    Matcher,
    compile_seeds,
    crumb_segments,
    haystack,
    lint_examples,
    lint_profile,
    lot_set_sha,
    normalise,
    order_candidates,
    shortlist,
)

KEYBOARD_BUCKET = {
    "name": "Keyboards & PC peripherals",
    "seeds": ["keyboard", "keycap", "key switch", "tkl", "gaming mouse",
              "mouse pad", "steelseries", "keychron"],
    "categories": ["Computers & Electronics - Computers - Peripherals - Keyboards / Mice"],
    "exclude": ["ignition key switch", "piano", "keyboard tray"],
}


def lot(title, **kw):
    rec = {"lot_number": kw.pop("lot_number", "S-1"), "title": title}
    rec.update(kw)
    return rec


def matches(bucket, item):
    m = Matcher(bucket["name"], bucket)
    return m.match(haystack(item), crumb_segments(item.get("category"))) is not None


# --------------------------------------------------------------------------
# The measured misses. Each of these got ZERO buckets from the un-prefiltered
# pass despite a brand or type word sitting in plain text in the title.


@pytest.mark.parametrize(
    "title",
    [
        "STEELSERIES APEX 3 TKL RGB KEYBOARD, BLACK",
        "KLIM CHROMA WIRELESS GAMING KEYBOARD RGB",
        "T8 60% GAMING KEYBOARD, 68 KEYS, USB-C CABLE",
        "MSI FORGE GK100 COMBO   KEYBOARD & MOUSE SET",
    ],
)
def test_known_brand_obvious_misses_are_shortlisted(title):
    assert matches(KEYBOARD_BUCKET, lot(title))


def test_lawn_mower_ignition_switch_is_not_a_keyboard():
    """The false positive that shipped: it was flagged Mechanical keyboards."""
    item = lot("ARAMOX LAWN MOWER IGNITION KEY SWITCH",
               category="Home & Garden - Lawn & Garden - Mowers")
    assert not matches(KEYBOARD_BUCKET, item)


def test_musical_keyboard_is_excluded():
    assert not matches(KEYBOARD_BUCKET, lot("ALESIS MELODY 61 MK4 KEYBOARD BUNDLE",
                                            model="61-key digital piano"))


def test_keyboard_tray_is_excluded():
    assert not matches(KEYBOARD_BUCKET, lot("VIVO KEYBOARD TRAY UNDER DESK, 27X11"))


# --------------------------------------------------------------------------
# Seed matching semantics


def test_left_anchored_prefix_matches_plurals_and_compounds():
    b = {"name": "b", "seeds": ["tote", "keyboard"]}
    assert matches(b, lot("STERILITE 18GAL STORAGE TOTES 4PK"))
    assert matches(b, lot("LOGITECH KEYBOARDS 2-PACK"))


def test_left_anchor_does_not_match_mid_word():
    b = {"name": "b", "seeds": ["key"]}
    assert not matches(b, lot("MONKEY BARS PLAYSET"))
    assert matches(b, lot("KEYBOARD, WIRELESS"))


def test_trailing_space_anchors_the_right_edge():
    """`pla ` must not match PLATED — it shortlisted 581 jewellery lots."""
    anchored = {"name": "b", "seeds": ["pla "]}
    assert not matches(anchored, lot("MFRYK GOLD LAYERED NECKLACE SET, 14K PLATED"))
    assert matches(anchored, lot("SUNLU PLA FILAMENT 1.75MM BLACK"))

    unanchored = {"name": "b", "seeds": ["pla"]}
    assert matches(unanchored, lot("MFRYK GOLD LAYERED NECKLACE SET, 14K PLATED"))


def test_hyphens_normalise_on_both_sides():
    """`pull up bar` must match "PULL-UP BAR"."""
    b = {"name": "b", "seeds": ["pull up bar"]}
    assert matches(b, lot("IBF IRON BODY FITNESS DOOR GYM   PULL-UP BAR"))
    assert normalise("Blu-ray / DVD") == "blu ray   dvd"


def test_exclude_beats_seed():
    b = {"name": "b", "seeds": ["keyboard"], "exclude": ["keyboard tray"]}
    assert not matches(b, lot("KEYBOARD TRAY UNDER DESK"))
    assert matches(b, lot("MECHANICAL KEYBOARD 60%"))


def test_empty_seed_list_compiles_to_none():
    assert compile_seeds([]) is None
    assert compile_seeds(["", "   "]) is None


# --------------------------------------------------------------------------
# The category axis — the only route to a lexically silent lot


def test_bare_sku_reached_only_by_breadcrumb():
    item = lot("64831", model="WL150",
               category="Computers & Electronics - Computers - Peripherals - Keyboards / Mice")
    assert matches(KEYBOARD_BUCKET, item)


def test_breadcrumb_matches_on_whole_segments_not_substrings():
    b = {"name": "b", "categories": ["Computers & Electronics - Computers"]}
    assert matches(b, lot("X", category="Computers & Electronics - Computers - Monitors"))
    # "Computer Desks" is a different segment and must not match "Computers".
    assert not matches(b, lot("X", category="Computers & Electronics - Computer Desks"))


def test_breadcrumb_prefix_shorter_than_lot_path_matches():
    b = {"name": "b", "categories": ["Home & Garden"]}
    assert matches(b, lot("X", category="Home & Garden - Lawn & Garden - Mowers"))
    assert not matches(b, lot("X", category="Business & Industrial - Medical"))


def test_lot_with_no_category_does_not_crash():
    b = {"name": "b", "categories": ["Home & Garden"]}
    assert not matches(b, lot("X"))


# --------------------------------------------------------------------------
# Coverage and ordering invariants


def test_base_row_has_exactly_the_four_required_keys():
    """A shorter row would replace the base row in merge_categorized and turn
    personal_match into null in the bundle."""
    row = dict(BASE_ROW, lot_number="S-1")
    assert set(row) == {"lot_number", "is_bats_list", "bats_buckets", "personal_match"}
    assert row["is_bats_list"] is False and row["personal_match"] is False


def test_shortlist_covers_every_lot_exactly_once():
    lots = [lot("KEYCHRON K2 KEYBOARD", lot_number="S-1"),
            lot("GARDEN HOSE 50FT", lot_number="S-2"),
            lot("UNRELATED WIDGET", lot_number="S-3")]
    cand, _, _ = shortlist(lots, [Matcher("kb", KEYBOARD_BUCKET)], [])
    base = [dict(BASE_ROW, lot_number=l["lot_number"]) for l in lots]
    assert len(base) == len(lots)
    assert {b["lot_number"] for b in base} == {"S-1", "S-2", "S-3"}
    assert set(cand) == {"S-1"}


def test_profile_pseudo_bucket_shortlists_outside_the_taxonomy():
    pseudo = Matcher("Pool & hot tub", {"name": "Pool & hot tub",
                                        "seeds": ["chlorine", "pool filter"]})
    lots = [lot("HTH CHLORINE TABLETS 5KG", lot_number="S-9")]
    cand, prof, _ = shortlist(lots, [], [pseudo])
    assert cand == {}
    assert prof == {"S-9": ["Pool & hot tub"]}


def test_ordering_groups_rarest_bucket_first_and_reports_boundaries():
    rows = [{"lot_number": "a", "cand": ["Big"]},
            {"lot_number": "b", "cand": ["Rare"]},
            {"lot_number": "c", "cand": ["Big"]}]
    ordered, boundaries = order_candidates(rows, {"Big": 400, "Rare": 3})
    assert [r["lot_number"] for r in ordered] == ["b", "a", "c"]
    assert boundaries == [("Rare", 0, 1), ("Big", 1, 2)]
    assert all("_primary" not in r for r in ordered)


def test_lot_set_sha_is_order_independent_and_content_sensitive():
    a = [{"lot_number": "S-1"}, {"lot_number": "S-2"}]
    assert lot_set_sha(a) == lot_set_sha(list(reversed(a)))
    assert lot_set_sha(a) != lot_set_sha(a + [{"lot_number": "S-3"}])


# --------------------------------------------------------------------------
# Lints


def test_lint_flags_bucket_no_interest_claims():
    buckets = [{"name": "Orphan"}]
    problems = lint_profile(buckets, [{"name": "I", "buckets": []}])
    assert any("claimed by no profile interest" in p for p in problems)


def test_lint_flags_interest_naming_a_missing_bucket():
    problems = lint_profile([{"name": "Real"}],
                            [{"name": "I", "buckets": ["Typo"]}])
    assert any("not in buckets.yaml" in p for p in problems)


def test_lint_catches_a_bucket_whose_seeds_miss_its_own_brands():
    warnings = lint_examples([{"name": "b", "examples": ["Keychron"], "seeds": ["keyboard"]}])
    assert warnings and "Keychron" in warnings[0]


def test_seed_exempt_silences_a_deliberately_unseeded_brand():
    assert lint_examples([{"name": "b", "examples": ["Corona"],
                           "seeds": ["pruner"], "seed_exempt": ["Corona"]}]) == []


def test_lint_examples_normalises_hyphenated_brands():
    """"Char-Broil" must be recognised by the seed `char-broil`."""
    assert lint_examples([{"name": "b", "examples": ["Char-Broil"],
                           "seeds": ["char-broil"]}]) == []
