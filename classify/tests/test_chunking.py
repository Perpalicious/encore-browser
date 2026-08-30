import json

import pytest

from classify import chunking
from classify.tests.conftest import lot


def test_split_is_lossless_and_ordered():
    lots = [lot(i) for i in range(1, 1201)]
    chunks = chunking.split_rows(lots)
    flat = [r for c in chunks for r in c]
    assert flat == lots, "chunking must preserve every row, in order"
    assert len({r["lot_number"] for r in flat}) == len(lots)


def test_row_limit_is_respected():
    chunks = chunking.split_rows([lot(i) for i in range(1, 1201)])
    assert all(len(c) <= chunking.MAX_ROWS for c in chunks)
    assert len(chunks) == 3


def test_split_is_deterministic():
    lots = [lot(i) for i in range(1, 700)]
    assert chunking.split_rows(lots) == chunking.split_rows(lots)


def test_byte_ceiling_closes_a_chunk_before_the_row_limit():
    """Verbose lots must not produce a pathological chunk that is still 500 rows."""
    fat = [lot(i, notes="x" * 4000) for i in range(1, 201)]
    chunks = chunking.split_rows(fat)
    assert all(len(c) < chunking.MAX_ROWS for c in chunks), "row limit should not bind here"
    for c in chunks:
        if len(c) > 1:
            assert sum(chunking.row_bytes(r) for r in c) <= chunking.MAX_BYTES


def test_a_single_oversized_row_still_gets_a_chunk():
    """A row is atomic — it cannot be split, so it must not be dropped."""
    lots = [lot(1), lot(2, notes="y" * (chunking.MAX_BYTES * 2)), lot(3)]
    chunks = chunking.split_rows(lots)
    flat = [r for c in chunks for r in c]
    assert len(flat) == 3


def test_max_rows_cannot_be_raised_above_the_cap():
    with pytest.raises(ValueError, match="hard maximum"):
        chunking.split_rows([lot(1)], max_rows=chunking.MAX_ROWS + 1)


def test_chunk_id_helpers():
    assert chunking.chunk_id("a", 7) == "a/007"
    assert chunking.child_ids("a/007") == ("a/007.0", "a/007.1")
    assert chunking.depth("a/007") == 0
    assert chunking.depth("a/007.1.0") == 2
    assert chunking.pass_of("a/007.1") == "a"
    assert chunking.filename("a/007.1") == "chunk_007.1.json"


def test_bisect_halves_left_biased():
    left, right = chunking.bisect([lot(i) for i in range(1, 8)])
    assert len(left) == 4 and len(right) == 3
