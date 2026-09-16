"""tools/recall_legend.py — the YAML → viewer JSON step and the history miner."""

from __future__ import annotations

from tools.recall_legend import (
    all_terms, candidate_terms, title_phrases, to_json, uncovered, validate,
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


def test_title_phrases_strip_brand_sizes_and_codes():
    assert title_phrases("SHARK WANDVAC HANDHELD VACUUM, WV200C") == ["wandvac handheld", "wandvac"]
    assert title_phrases("KIMLLIER 8 PACK TIE DOWN STRAPS 2\" X 15'") == ["tie down", "tie"]
    # two words: nothing to treat as a brand
    assert title_phrases("GARDEN HOSE") == ["garden hose", "garden"]
    assert title_phrases("") == []


def test_candidate_terms_count_by_signal():
    rows = [
        {"title": "VEVOR RATCHET STRAPS 4PK", "signal": "bid"},
        {"title": "KIMLLIER RATCHET STRAPS 1.5\" X15'", "signal": "watch"},
        {"title": "ignored", "signal": ""},
    ]
    counts = candidate_terms(rows)
    assert counts["ratchet straps"] == {"bid": 1, "watch": 1}


def test_uncovered_applies_substring_both_ways_and_weights_bids():
    cands = {
        "ratchet straps": {"bid": 1, "watch": 0},   # covered by "ratchet"
        "hose": {"bid": 0, "watch": 1},             # covered by "garden hose"
        "heat gun": {"bid": 1, "watch": 1},
        "water table": {"bid": 0, "watch": 4},
    }
    out = uncovered(cands, ["ratchet", "garden hose"])
    assert [(p, s) for p, _, _, s in out] == [("water table", 4), ("heat gun", 3)]
