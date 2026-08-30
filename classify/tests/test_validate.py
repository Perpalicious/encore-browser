import json

import pytest

from classify.validate import ChunkRejected, validate_output

KNOWN = {"Hand tools", "Board games", "Electronics"}
TAGS = {"diy", "garage"}


def run(tmp_path, payload, *, expected=("S-1", "S-2", "S-3"), bucket_count=3):
    path = tmp_path / "out.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return validate_output(
        path, chunk_id="a/000", fingerprint="fp", expected_lots=list(expected),
        bucket_count=bucket_count, known_buckets=KNOWN, tag_vocab=TAGS,
    )


def envelope(**over):
    payload = {"chunk_id": "a/000", "fingerprint": "fp", "buckets_seen": 3,
               "matches": [], "no_match": ["S-1", "S-2", "S-3"]}
    payload.update(over)
    return payload


def flagged(lot="S-1", buckets=("Hand tools",), **over):
    row = {"lot_number": lot, "is_bats_list": True, "bats_buckets": list(buckets),
           "personal_match": False, "bats_subtype": "screwdrivers"}
    row.update(over)
    return row


def test_all_no_match_is_accepted_and_expands(tmp_path):
    rows, warnings = run(tmp_path, envelope())
    assert [r["lot_number"] for r in rows] == ["S-1", "S-2", "S-3"]
    assert all(r["is_bats_list"] is False for r in rows)
    assert warnings == []


def test_a_missing_lot_is_rejected_and_named(tmp_path):
    with pytest.raises(ChunkRejected) as exc:
        run(tmp_path, envelope(no_match=["S-1", "S-2"]))
    assert "1 of 3 lots missing" in str(exc.value)
    assert "S-3" in str(exc.value)


def test_a_lot_in_both_lists_is_rejected(tmp_path):
    with pytest.raises(ChunkRejected, match="in both matches and no_match"):
        run(tmp_path, envelope(matches=[flagged("S-1")],
                               no_match=["S-1", "S-2", "S-3"]))


def test_a_lot_not_in_this_chunk_is_rejected(tmp_path):
    with pytest.raises(ChunkRejected, match="not in this chunk"):
        run(tmp_path, envelope(no_match=["S-1", "S-2", "S-3", "S-99"]))


def test_duplicate_lot_numbers_are_rejected(tmp_path):
    with pytest.raises(ChunkRejected, match="more than once"):
        run(tmp_path, envelope(no_match=["S-1", "S-1", "S-2", "S-3"]))


def test_unknown_bucket_name_is_rejected(tmp_path):
    """verify_passes.py hard-fails on these; catching it here saves three steps."""
    with pytest.raises(ChunkRejected, match="not in buckets.yaml"):
        run(tmp_path, envelope(matches=[flagged("S-1", ("Hand Tools",))],
                               no_match=["S-2", "S-3"]))


def test_buckets_seen_mismatch_is_rejected(tmp_path):
    """The automated stand-in for 'tell me how many buckets you read'."""
    with pytest.raises(ChunkRejected, match="did not read the whole taxonomy"):
        run(tmp_path, envelope(buckets_seen=62))


def test_buckets_seen_is_compared_to_the_fixture_not_a_hardcoded_62(tmp_path):
    rows, _ = run(tmp_path, envelope(buckets_seen=3), bucket_count=3)
    assert len(rows) == 3


def test_fingerprint_mismatch_is_rejected(tmp_path):
    with pytest.raises(ChunkRejected, match="different configuration"):
        run(tmp_path, envelope(fingerprint="stale"))


def test_chunk_id_mismatch_is_rejected(tmp_path):
    with pytest.raises(ChunkRejected, match="chunk_id"):
        run(tmp_path, envelope(chunk_id="a/001"))


def test_markdown_fenced_output_is_rejected(tmp_path):
    path = tmp_path / "out.json"
    path.write_text("```json\n{}\n```", encoding="utf-8")
    with pytest.raises(ChunkRejected, match="not valid JSON"):
        validate_output(path, chunk_id="a/000", fingerprint="fp",
                        expected_lots=["S-1"], bucket_count=3,
                        known_buckets=KNOWN, tag_vocab=TAGS)


def test_a_bare_array_is_rejected(tmp_path):
    """The old per-lot array shape must not be silently accepted."""
    path = tmp_path / "out.json"
    path.write_text(json.dumps([{"lot_number": "S-1"}]), encoding="utf-8")
    with pytest.raises(ChunkRejected, match="expected a JSON object"):
        validate_output(path, chunk_id="a/000", fingerprint="fp",
                        expected_lots=["S-1"], bucket_count=3,
                        known_buckets=KNOWN, tag_vocab=TAGS)


def test_stray_personal_tag_warns_but_does_not_reject(tmp_path):
    """verify_passes.py treats this as informational; bisecting over it would churn."""
    pick = {"lot_number": "S-1", "is_bats_list": False, "bats_buckets": [],
            "personal_match": True, "personal_tags": ["woodworking"],
            "match_strength": "weak", "personal_reasoning": "fits"}
    rows, warnings = run(tmp_path, envelope(matches=[pick], no_match=["S-2", "S-3"]))
    assert len(rows) == 3
    assert any("outside profile.yaml" in w for w in warnings)


def test_one_bucket_per_lot_across_many_flags_warns(tmp_path):
    lots = [f"S-{i}" for i in range(1, 31)]
    matches = [flagged(l) for l in lots]
    rows, warnings = run(tmp_path, envelope(matches=matches, no_match=[]),
                         expected=tuple(lots))
    assert len(rows) == 30
    assert any("one-bucket-per-lot" in w for w in warnings)
