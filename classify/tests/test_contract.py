import pytest
from pydantic import ValidationError

from classify.contract import (
    BASE_ROW, FORBIDDEN_KEYS, PERSONAL_ONLY_KEYS, ChunkResponse, MatchRow,
    base_row, expand,
)


def match(**over):
    row = dict(lot_number="S-1", is_bats_list=True, bats_buckets=["Hand tools"],
               personal_match=False, bats_subtype="screwdrivers")
    row.update(over)
    return row


def test_a_valid_row_round_trips_without_none_keys():
    row = MatchRow(**match()).to_row()
    assert row == match()
    assert "personal_tags" not in row, "None fields must not reach the output file"


@pytest.mark.parametrize("key", sorted(FORBIDDEN_KEYS))
def test_each_forbidden_key_is_rejected(key):
    """bats_category alone flips build/transform.py into Shape B; all six are barred."""
    with pytest.raises(ValidationError):
        MatchRow(**match(**{key: "anything"}))


def test_is_bats_list_must_agree_with_bats_buckets():
    with pytest.raises(ValidationError, match="is_bats_list must equal"):
        MatchRow(**match(is_bats_list=False, bats_buckets=["Hand tools"],
                         bats_subtype=None, personal_match=True))
    with pytest.raises(ValidationError, match="is_bats_list must equal"):
        MatchRow(**match(is_bats_list=True, bats_buckets=[]))


def test_subtype_required_when_flagged():
    with pytest.raises(ValidationError, match="bats_subtype is required"):
        MatchRow(**match(bats_subtype=None))
    # A whitespace-only subtype is absent as far as the drill-down is concerned.
    with pytest.raises(ValidationError, match="bats_subtype is required"):
        MatchRow(**match(bats_subtype="   "))


def test_subtype_forbidden_when_not_flagged():
    with pytest.raises(ValidationError, match="must be omitted"):
        MatchRow(**match(is_bats_list=False, bats_buckets=[], personal_match=True,
                         bats_subtype="screwdrivers"))


def test_subtype_must_be_a_label_not_a_sentence():
    with pytest.raises(ValidationError, match="label, not a sentence"):
        MatchRow(**match(bats_subtype="a really quite long descriptive phrase here"))


def test_personal_match_must_be_a_real_boolean():
    """PROMPTS.md: not the string "true", not 1 — only a real boolean counts."""
    for bad in ("true", 1):
        with pytest.raises(ValidationError):
            MatchRow(**match(personal_match=bad))


@pytest.mark.parametrize("key", PERSONAL_ONLY_KEYS)
def test_personal_only_keys_rejected_when_not_a_pick(key):
    value = "strong" if key == "match_strength" else (
        ["x"] if key in ("personal_tags", "match_types") else "because")
    with pytest.raises(ValidationError, match="must be omitted"):
        MatchRow(**match(**{key: value}))


def test_match_strength_enum():
    with pytest.raises(ValidationError):
        MatchRow(**match(personal_match=True, match_strength="very strong"))


def test_a_row_that_matches_nothing_belongs_in_no_match():
    with pytest.raises(ValidationError, match="matches nothing"):
        MatchRow(lot_number="S-1", is_bats_list=False, bats_buckets=[],
                 personal_match=False)


def test_personal_pick_without_buckets_is_valid():
    """profile.yaml has interests with no bucket of their own."""
    row = MatchRow(lot_number="S-1", is_bats_list=False, bats_buckets=[],
                   personal_match=True, personal_tags=["diy"],
                   match_strength="weak", personal_reasoning="fits the garage build")
    assert row.to_row()["personal_match"] is True


def test_base_row_shape_is_the_four_load_bearing_keys():
    assert base_row("S-9") == dict(BASE_ROW, lot_number="S-9")
    assert set(base_row("S-9")) == {
        "lot_number", "is_bats_list", "bats_buckets", "personal_match"}


def test_expand_covers_every_lot_exactly_once():
    resp = ChunkResponse(chunk_id="a/000", fingerprint="f", buckets_seen=3,
                         matches=[MatchRow(**match())], no_match=["S-2", "S-3"])
    rows = expand(resp)
    assert [r["lot_number"] for r in rows] == ["S-1", "S-2", "S-3"]
    assert all(set(r) >= set(BASE_ROW) for r in rows)


def test_envelope_rejects_unknown_top_level_keys():
    with pytest.raises(ValidationError):
        ChunkResponse(chunk_id="a/000", fingerprint="f", buckets_seen=3,
                      matches=[], no_match=[], notes="chatty preamble")
