"""tools/recall_legend.py — the YAML → viewer JSON step, the term check, and the history miner."""

from __future__ import annotations

from tools.recall_legend import (
    all_terms, candidate_brands, normalize, term_flags, term_stats, title_brand,
    to_json, uncovered, validate,
)


def test_validate_accepts_a_clean_legend():
    assert validate([{"name": "Tools", "terms": ["clamps", "tie downs"]}]) == []


def test_validate_catches_empty_terms_groups_and_duplicates():
    problems = validate([
        {"name": "Tools", "terms": ["clamps", " "]},
        {"name": "Garden", "terms": ["Clamps"]},
        {"name": "Empty", "terms": []},
        {"terms": ["x"]},
    ])
    assert any("empty term" in p for p in problems)
    assert any("duplicates" in p and "Tools" in p for p in problems)
    assert any("Empty: no terms" in p for p in problems)
    assert any("missing name" in p for p in problems)


def test_to_json_trims_and_keeps_order():
    out = to_json([{"name": " Tools ", "terms": [" clamps", "tie downs "]}])
    assert out == {"groups": [{"name": "Tools", "terms": ["clamps", "tie downs"]}]}
    assert all_terms([{"name": "T", "terms": ["Clamps"]}]) == ["clamps"]


def test_title_brand_takes_the_leading_word_unless_it_is_a_code_or_filler():
    assert title_brand("SHARK WANDVAC HANDHELD VACUUM, WV200C") == "shark"
    assert title_brand("BLACK+DECKER DUSTBUSTER REVEAL") == "black+decker"
    assert title_brand("MEGUIAR'S GOLD CLASS CAR WASH") == "meguiar's"
    assert title_brand("12PK TIE DOWN STRAPS") is None
    assert title_brand("SET OF 4 BINS") is None
    assert title_brand("") is None


def test_candidate_brands_count_by_signal():
    rows = [
        {"title": "SHARK WANDVAC HANDHELD", "signal": "bid"},
        {"title": "SHARK HD430C FLEXSTYLE", "signal": "watch"},
        {"title": "SHARK ignored", "signal": ""},
    ]
    assert candidate_brands(rows) == {"shark": {"bid": 1, "watch": 1}}


def _lot(title, flagged=False):
    return {"title": title, "lot_number": "1", "bat_buckets": ["X"] if flagged else []}


def test_term_stats_mirror_the_viewer_search_and_count_the_gap():
    lots = [
        _lot("STANLEY QUENCHER 40OZ", flagged=True),
        _lot("STANLEY ICEFLOW BOTTLE"),
        _lot("KEURIG K-MINI COFFEE MAKER"),
    ]
    weeks = [["STANLEY QUENCHER"], ["SHUN CLASSIC 8IN CHEF KNIFE"], []]
    stats = term_stats(["stanley", "shun", "keurig k-mini", "hexclad"], lots, weeks)
    assert stats["stanley"] == {"weeks": 1, "now": 2, "missed": 1, "whole": 2}
    assert stats["shun"]["weeks"] == 1 and stats["shun"]["now"] == 0
    # every token must be present, in any order — the viewer's AND rule
    assert stats["keurig k-mini"]["now"] == 1
    assert term_flags(stats["hexclad"]) == ["never seen"]
    assert term_flags(stats["stanley"]) == []


def test_term_flags_noisy_substrings_but_not_plurals():
    lots = [_lot(t) for t in [
        "LEGO CITY 60430", "LEGO FRIENDS", "LEGO STAR WARS", "LEGO SPEED", "BORREGO SHOCKS",
        "EGO 56V BLOWER",
    ]]
    lots += [_lot("SQUISHMALLOWS 8IN")] * 5
    stats = term_stats(["ego", "squishmallow"], lots, [["EGO 56V BLOWER", "SQUISHMALLOWS"]])
    assert term_flags(stats["ego"]) == ["noisy (1 as a word)"]
    assert term_flags(stats["squishmallow"]) == []


def test_normalize_matches_the_viewer():
    assert normalize("WÜSTHOF Classic") == "wusthof classic"


def test_uncovered_applies_substring_both_ways_and_weights_bids():
    cands = {
        "shark": {"bid": 1, "watch": 0},        # covered by "shark"
        "philips": {"bid": 0, "watch": 1},      # covered by "philips hue"
        "vevor": {"bid": 1, "watch": 1},
        "razer": {"bid": 0, "watch": 4},
    }
    out = uncovered(cands, ["shark", "philips hue"])
    assert [(p, s) for p, _, _, s in out] == [("razer", 4), ("vevor", 3)]
