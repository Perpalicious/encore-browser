"""Tests for tools/chunk_flagging.py and tools/expand_flags.py.

These two tools replace the manual "paste the whole pass and hope it finishes"
flagging step. Between them they make three promises, and every test here
guards one of them:

  1. Dedup loses no coverage. Every lot in the auction comes back with a row,
     even though the model only ever sees one representative per product.
  2. A response can only speak about its own chunk. Anything else — a
     hallucinated lot, the wrong file saved, a lot judged twice — is a hard
     error, not a row that quietly merges.
  3. A truncated response is detected. The pass returns matches only, so
     "short" is indistinguishable from "few matches" without the sentinel.

Failure must write nothing. build/ is lenient by design, so a partial
_flags.json would produce a clean, successful build quietly missing its flags.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import chunk_flagging, expand_flags
from tools.chunk_flagging import boundary_key, split_rows

BUCKETS = """\
buckets:
  - name: Bath towels
    group: Home
    description: Towels.
  - name: Board games
    group: Toys
    description: Games.
"""

PROFILE = """\
sizes:
  shirt: M
interests:
  - board games
"""


def _lot(n, title, condition="Excellent", category="Home Goods & Decor - Home Goods"):
    return {
        "lot_number": str(n),
        "title": title,
        "condition": condition,
        "category": category,
        "est_retail_price": 10.0,
    }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A minimal repo layout: the tools resolve paths relative to cwd."""
    (tmp_path / "data" / "categorized").mkdir(parents=True)
    (tmp_path / "buckets.yaml").write_text(BUCKETS)
    (tmp_path / "profile.yaml").write_text(PROFILE)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_slim(repo, lots, auction="X"):
    path = repo / "data" / "categorized" / f"auction_{auction}_for_agent.json"
    path.write_text(json.dumps(lots))
    return path


def read(repo, name):
    return json.loads((repo / "data" / "categorized" / name).read_text())


def respond(repo, n, matches, last_lot, auction="X"):
    """Save a simulated ChatGPT response for chunk n."""
    rows = list(matches) + [{"chunk_complete": str(last_lot)}]
    (repo / "data" / "categorized"
     / f"auction_{auction}_chunk_{n:02d}_flags.json").write_text(json.dumps(rows))


def match_row(lot, buckets=("Bath towels",)):
    return {
        "lot_number": str(lot),
        "is_bats_list": True,
        "bats_buckets": list(buckets),
        "bats_subtype": "hand towels",
        "personal_match": False,
    }


class TestDedup:
    def test_identical_products_collapse_to_one_representative(self, repo):
        write_slim(repo, [_lot(i, "REVLON ONE-STEP DRYER") for i in range(1, 6)])
        chunk_flagging.main("X", rows_per_chunk=100)
        assert len(read(repo, "auction_X_chunk_01.json")) == 1

    def test_fan_out_covers_every_lot_exactly_once(self, repo):
        lots = [_lot(i, "REVLON ONE-STEP DRYER") for i in range(1, 6)]
        lots += [_lot(i, f"THING {i}") for i in range(6, 11)]
        write_slim(repo, lots)
        chunk_flagging.main("X", rows_per_chunk=100)
        groups = read(repo, "auction_X_flag_groups.json")
        covered = [lot for members in groups.values() for lot in members]
        assert sorted(covered, key=int) == [str(i) for i in range(1, 11)]
        assert len(covered) == len(set(covered))

    def test_condition_splits_a_group(self, repo):
        """A sealed unit must never inherit a broken one's judgment."""
        write_slim(repo, [
            _lot(1, "SHARK FLEXSTYLE", condition="Brand New - Sealed"),
            _lot(2, "SHARK FLEXSTYLE", condition="For Parts Only"),
        ])
        chunk_flagging.main("X", rows_per_chunk=100)
        assert len(read(repo, "auction_X_chunk_01.json")) == 2

    def test_qty_reports_the_group_size(self, repo):
        write_slim(repo, [_lot(i, "REVLON ONE-STEP DRYER") for i in range(1, 130)])
        chunk_flagging.main("X", rows_per_chunk=100)
        assert read(repo, "auction_X_chunk_01.json")[0]["qty"] == 129

    def test_rerun_is_deterministic(self, repo):
        write_slim(repo, [_lot(i, f"THING {i % 7}") for i in range(1, 40)])
        chunk_flagging.main("X", rows_per_chunk=5)
        first = read(repo, "auction_X_chunk_01.json")
        chunk_flagging.main("X", rows_per_chunk=5)
        assert read(repo, "auction_X_chunk_01.json") == first


class TestChunking:
    def test_chunks_partition_the_products_losslessly(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 26)])
        chunk_flagging.main("X", rows_per_chunk=10)
        seen = []
        for n in (1, 2, 3):
            seen += [r["lot_number"] for r in read(repo, f"auction_X_chunk_{n:02d}.json")]
        assert sorted(seen, key=int) == [str(i) for i in range(1, 26)]
        assert len(seen) == len(set(seen))

    def test_chunks_are_category_ordered(self, repo):
        """Boundaries fall inside a category, so a chunk is mostly one thing."""
        lots = [_lot(i, f"TOOL {i}", category="Lawn & Garden") for i in range(1, 11)]
        lots += [_lot(i, f"TOWEL {i}", category="Home Goods") for i in range(11, 21)]
        write_slim(repo, lots)
        chunk_flagging.main("X", rows_per_chunk=10)
        first = {r["category"] for r in read(repo, "auction_X_chunk_01.json")}
        assert first == {"Home Goods"}

    def test_stale_chunks_from_a_shorter_run_are_removed(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 31)])
        chunk_flagging.main("X", rows_per_chunk=10)
        assert (repo / "data/categorized/auction_X_chunk_03.json").exists()
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 11)])
        chunk_flagging.main("X", rows_per_chunk=10)
        assert not (repo / "data/categorized/auction_X_chunk_02.json").exists()

    def test_context_carries_both_config_files(self, repo):
        write_slim(repo, [_lot(1, "THING")])
        chunk_flagging.main("X", rows_per_chunk=10)
        text = (repo / "data/categorized/context.yaml").read_text()
        assert "Bath towels" in text and "board games" in text
        assert "buckets.yaml" in text and "profile.yaml" in text


class TestBoundarySnapping:
    """A cut must not land inside a run of near-identical products.

    Dedup guarantees that *identical* products share one judgment. Near-
    identical ones (the FlexStyle styler and the FlexStyle filters) are
    separate rows, and sending them to two different chats is the one place
    this design can produce inconsistent answers for near-identical things.
    """

    def test_boundary_key_groups_leading_title_words(self):
        a = _lot(1, "SHARK FLEXSTYLE AIR STYLING SYSTEM")
        b = _lot(2, "SHARK FLEXSTYLE CURLY DEFINER")
        c = _lot(3, "SHARK NAVIGATOR VACUUM")
        assert boundary_key(a) == boundary_key(b)
        assert boundary_key(a) != boundary_key(c)

    def test_boundary_key_separates_categories(self):
        a = _lot(1, "SHARK FLEXSTYLE", category="Home Goods")
        b = _lot(2, "SHARK FLEXSTYLE", category="Lawn & Garden")
        assert boundary_key(a) != boundary_key(b)

    def test_a_run_is_not_split(self):
        """Target lands at row 10, mid-run; the cut must move off it."""
        rows = [_lot(i, f"ALPHA THING {i}") for i in range(1, 9)]
        rows += [_lot(i, f"SHARK FLEXSTYLE VARIANT {i}") for i in range(9, 15)]
        rows += [_lot(i, f"ZEBRA THING {i}") for i in range(15, 21)]
        chunks, forced = split_rows(rows, 10, drift=4)
        assert forced == 0
        for first, second in zip(chunks, chunks[1:]):
            assert boundary_key(first[-1]) != boundary_key(second[0])

    def test_the_drift_window_bounds_how_far_a_cut_moves(self):
        """A boundary just outside the window is not chased.

        The window is what stops snapping from distorting chunk sizes: with
        production numbers (2,750 rows, 275 window) the longest measured run
        is 75, so it never binds — but it must still hold if that changes.
        """
        rows = [_lot(i, f"ALPHA THING {i}") for i in range(1, 9)]
        rows += [_lot(i, f"SHARK FLEXSTYLE VARIANT {i}") for i in range(9, 15)]
        rows += [_lot(i, f"ZEBRA THING {i}") for i in range(15, 21)]
        chunks, forced = split_rows(rows, 10, drift=1)
        assert forced == 1
        assert len(chunks[0]) == 10

    def test_snapping_preserves_every_row_exactly_once(self):
        rows = [_lot(i, f"BRAND {i // 4} ITEM {i}") for i in range(1, 61)]
        chunks, _ = split_rows(rows, 10)
        seen = [r["lot_number"] for c in chunks for r in c]
        assert sorted(seen, key=int) == [str(i) for i in range(1, 61)]
        assert len(seen) == len(set(seen))

    def test_chunk_sizes_stay_near_the_target(self):
        rows = [_lot(i, f"BRAND {i // 3} ITEM {i}") for i in range(1, 101)]
        chunks, _ = split_rows(rows, 20)
        drift = max(1, int(20 * chunk_flagging.BOUNDARY_DRIFT))
        for c in chunks[:-1]:
            assert abs(len(c) - 20) <= drift

    def test_a_run_longer_than_the_window_is_reported_not_hidden(self):
        """No boundary reachable — cut mid-run, but say so."""
        rows = [_lot(i, "SAME TITLE FOREVER") for i in range(1, 41)]
        chunks, forced = split_rows(rows, 10, drift=4)
        assert forced >= 1
        assert sum(len(c) for c in chunks) == 40

    def test_single_chunk_needs_no_snapping(self):
        rows = [_lot(i, f"THING {i}") for i in range(1, 6)]
        chunks, forced = split_rows(rows, 10)
        assert len(chunks) == 1 and forced == 0


class TestExpandHappyPath:
    def test_match_fans_out_to_every_lot_in_the_group(self, repo):
        write_slim(repo, [_lot(i, "REVLON ONE-STEP DRYER") for i in range(1, 6)])
        chunk_flagging.main("X", rows_per_chunk=10)
        rep = read(repo, "auction_X_chunk_01.json")[0]["lot_number"]
        respond(repo, 1, [match_row(rep)], rep)
        expand_flags.main("X")
        rows = read(repo, "auction_X_flags.json")
        assert len(rows) == 5
        assert all(r["is_bats_list"] and r["bats_buckets"] == ["Bath towels"]
                   for r in rows)
        assert all(r["bats_subtype"] == "hand towels" for r in rows)

    def test_unmatched_product_gets_the_all_false_row(self, repo):
        write_slim(repo, [_lot(1, "A"), _lot(2, "B")])
        chunk_flagging.main("X", rows_per_chunk=10)
        chunk = read(repo, "auction_X_chunk_01.json")
        respond(repo, 1, [], chunk[-1]["lot_number"])
        expand_flags.main("X")
        rows = read(repo, "auction_X_flags.json")
        assert len(rows) == 2
        for r in rows:
            assert r["is_bats_list"] is False
            assert r["bats_buckets"] == []
            assert r["personal_match"] is False

    def test_every_lot_gets_a_row_across_several_chunks(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 26)])
        chunk_flagging.main("X", rows_per_chunk=10)
        for n in (1, 2, 3):
            chunk = read(repo, f"auction_X_chunk_{n:02d}.json")
            respond(repo, n, [match_row(chunk[0]["lot_number"])],
                    chunk[-1]["lot_number"])
        expand_flags.main("X")
        rows = read(repo, "auction_X_flags.json")
        assert sorted(r["lot_number"] for r in rows) == sorted(
            str(i) for i in range(1, 26))
        assert sum(1 for r in rows if r["is_bats_list"]) == 3


class TestExpandRejects:
    """Each of these produces a clean-looking build if it slips through."""

    @pytest.fixture
    def one_chunk(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 6)])
        chunk_flagging.main("X", rows_per_chunk=10)
        return read(repo, "auction_X_chunk_01.json")

    def _fails(self, repo, message):
        with pytest.raises(SystemExit) as exc:
            expand_flags.main("X")
        assert message in str(exc.value)
        assert not (repo / "data/categorized/auction_X_flags.json").exists()

    def test_missing_sentinel_is_truncation(self, repo, one_chunk):
        (repo / "data/categorized/auction_X_chunk_01_flags.json").write_text(
            json.dumps([match_row(one_chunk[0]["lot_number"])]))
        self._fails(repo, "chunk_complete")

    def test_sentinel_naming_an_earlier_lot_is_an_early_stop(self, repo, one_chunk):
        respond(repo, 1, [match_row(one_chunk[0]["lot_number"])],
                one_chunk[0]["lot_number"])
        self._fails(repo, "stopped early")

    def test_sentinel_must_be_last(self, repo, one_chunk):
        rows = [{"chunk_complete": one_chunk[-1]["lot_number"]},
                match_row(one_chunk[0]["lot_number"])]
        (repo / "data/categorized/auction_X_chunk_01_flags.json").write_text(
            json.dumps(rows))
        self._fails(repo, "not the last element")

    def test_lot_from_another_chunk_is_rejected(self, repo, one_chunk):
        respond(repo, 1, [match_row("ZZZ-999")], one_chunk[-1]["lot_number"])
        self._fails(repo, "not in this chunk")

    def test_forbidden_key_is_rejected(self, repo, one_chunk):
        row = match_row(one_chunk[0]["lot_number"])
        row["bats_category"] = "Home"
        respond(repo, 1, [row], one_chunk[-1]["lot_number"])
        self._fails(repo, "forbidden key")

    def test_missing_required_key_is_rejected(self, repo, one_chunk):
        row = match_row(one_chunk[0]["lot_number"])
        del row["personal_match"]
        respond(repo, 1, [row], one_chunk[-1]["lot_number"])
        self._fails(repo, "personal_match")

    def test_flag_without_buckets_is_rejected(self, repo, one_chunk):
        row = match_row(one_chunk[0]["lot_number"])
        row["bats_buckets"] = []
        respond(repo, 1, [row], one_chunk[-1]["lot_number"])
        self._fails(repo, "is_bats_list")

    def test_same_lot_twice_in_one_chunk_is_rejected(self, repo, one_chunk):
        lot = one_chunk[0]["lot_number"]
        respond(repo, 1, [match_row(lot), match_row(lot)], one_chunk[-1]["lot_number"])
        self._fails(repo, "returned twice")

    def test_missing_response_file_is_rejected(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 26)])
        chunk_flagging.main("X", rows_per_chunk=10)
        chunk = read(repo, "auction_X_chunk_01.json")
        respond(repo, 1, [], chunk[-1]["lot_number"])
        self._fails(repo, "no response saved")

    def test_truncated_json_is_rejected(self, repo, one_chunk):
        (repo / "data/categorized/auction_X_chunk_01_flags.json").write_text(
            '[{"lot_number": "1", "is_bats_')
        self._fails(repo, "not valid JSON")

    def test_no_chunks_at_all_is_rejected(self, repo):
        with pytest.raises(SystemExit) as exc:
            expand_flags.main("X")
        assert "no chunk files" in str(exc.value)
