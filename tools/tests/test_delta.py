"""Tests for tools/delta.py — the mid-week delta loop.

Two promises: `start` only ever hands the chats lots nobody has judged yet
(not the week's, not an earlier delta's), and `merge` produces a categorized
file `verify_passes.py` accepts — every row in the current lot set, the fresh
`lot_set_sha` carried, lots pulled between scrapes dropped rather than
counted as additions, and a foreign row fatal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import delta


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _raw(n: int, first_seen: str | None = "2026-09-15T22:00:00+00:00") -> dict:
    item = {"id": 1000 + n, "lot_number": str(n), "title": f"Lot {n}"}
    if first_seen:
        item["first_seen"] = first_seen
    return item


def _flag(n: int, bat: bool = False) -> dict:
    return {"lot_number": str(n), "is_bats_list": bat,
            "bats_buckets": ["Lego"] if bat else [], "personal_match": False}


# --- pure helpers ---------------------------------------------------------

def test_next_delta_n(tmp_path):
    assert delta.next_delta_n("77", tmp_path) == 1
    for n in (1, 2, 10):
        _write(tmp_path / f"auction_77_d{n}.json", {"items": []})
    # a sibling ID's deltas and a stray chunk file must not count
    _write(tmp_path / "auction_77_d3_chunk_01.json", {"items": []})
    _write(tmp_path / "auction_778_d4.json", {"items": []})
    assert [n for n, _ in delta.delta_paths("77", tmp_path)] == [1, 2, 10]
    assert delta.next_delta_n("77", tmp_path) == 11


def test_known_keys_covers_ids_lot_numbers_and_prior_deltas():
    keys = delta.known_keys([{"lot_number": "1", "id": 5}], [{"id": 9}], [{"lot_number": ""}])
    assert keys == {"1", "5", "9"}


def test_restrict_reports_dropped_lots():
    kept, dropped = delta.restrict([_flag(1), _flag(2), _flag(3)], {"1", "3"})
    assert [k["lot_number"] for k in kept] == ["1", "3"]
    assert dropped == ["2"]


def test_fold_applies_layers_and_drops_pulled_lots_first():
    base = [_flag(1), _flag(2), _flag(3)]
    week = [_flag(1, bat=True), _flag(9)]          # lot 9 was pulled since
    d1 = [_flag(3, bat=True)]
    items, report = delta.fold(base, [("categorized", week), ("d1", d1)], {"1", "2", "3"})
    assert [i["is_bats_list"] for i in items] == [True, False, True]
    assert "dropped 1" in report[0] and "dropped 0" in report[1]


def test_fold_rejects_a_row_the_base_does_not_know():
    with pytest.raises(delta.DeltaError):
        delta.fold([_flag(1)], [("d1", [_flag(2)])], {"1", "2"})


# --- start ------------------------------------------------------------------

@pytest.fixture
def week(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(Path("data/raw/auction_77.json"),
           {"scraped_at": "2026-09-15T22:00:00+00:00",
            "items": [_raw(1, "2026-09-13T21:00:00+00:00"), _raw(2, "2026-09-13T21:00:00+00:00"),
                      _raw(3), _raw(4)]})
    _write(Path("data/categorized/auction_77_categorized.json"),
           {"lot_set_sha": "old", "items": [_flag(1, bat=True), _flag(2)]})
    return tmp_path


def test_start_writes_only_unjudged_lots(week, capsys):
    delta.start("77")
    out = json.loads(Path("data/raw/auction_77_d1.json").read_text())
    assert out["parent"] == "77" and out["delta"] == 1 and out["item_count"] == 2
    assert [i["lot_number"] for i in out["items"]] == ["3", "4"]
    assert "tools/chunk_flagging.py 77_d1" in capsys.readouterr().out


def test_start_excludes_lots_already_in_an_earlier_delta(week):
    delta.start("77")
    # Thursday: lot 5 arrives before d1's chats were run.
    raw = json.loads(Path("data/raw/auction_77.json").read_text())
    raw["items"].append(_raw(5))
    _write(Path("data/raw/auction_77.json"), raw)
    delta.start("77")
    out = json.loads(Path("data/raw/auction_77_d2.json").read_text())
    assert [i["lot_number"] for i in out["items"]] == ["5"]


def test_start_refuses_when_nothing_is_new(week):
    _write(Path("data/categorized/auction_77_categorized.json"),
           {"items": [_flag(n) for n in (1, 2, 3, 4)]})
    with pytest.raises(SystemExit, match="Nothing to do"):
        delta.start("77")


def test_start_refuses_lots_without_first_seen(week):
    raw = json.loads(Path("data/raw/auction_77.json").read_text())
    del raw["items"][2]["first_seen"]
    _write(Path("data/raw/auction_77.json"), raw)
    with pytest.raises(SystemExit, match="first_seen"):
        delta.start("77")
    assert not Path("data/raw/auction_77_d1.json").exists()


# --- merge (fold only; slim/prefilter are exercised by their own tests) -----

@pytest.fixture
def judged(week):
    delta.start("77")
    # Pretend slim + prefilter ran on the full raw, except lot 2 was pulled.
    _write(Path("data/categorized/auction_77_base.json"),
           {"lot_set_sha": "fresh", "items": [_flag(1), _flag(3), _flag(4)]})
    _write(Path("data/categorized/auction_77_d1_for_agent.json"),
           [{"lot_number": "3"}, {"lot_number": "4"}])
    _write(Path("data/categorized/auction_77_d1_flags.json"), [_flag(3, bat=True), _flag(4)])
    _write(Path("data/categorized/auction_77_resale.json"),
           [{"lot_number": "1", "est_resale_low": 5, "est_resale_high": 9},
            {"lot_number": "2", "est_resale_low": 1, "est_resale_high": 2}])
    _write(Path("data/categorized/auction_77_d1_resale.json"),
           [{"lot_number": "3", "est_resale_low": 20, "est_resale_high": 30}])
    return week


def test_merge_folds_onto_the_fresh_base_and_is_idempotent(judged):
    delta.merge("77", run_tools=False)
    cat = json.loads(Path("data/categorized/auction_77_categorized.json").read_text())
    assert cat["lot_set_sha"] == "fresh" and cat["deltas"] == [1]
    assert {i["lot_number"]: i["is_bats_list"] for i in cat["items"]} == {
        "1": True, "3": True, "4": False}          # lot 2 dropped, not added back
    resale = json.loads(Path("data/categorized/auction_77_resale.json").read_text())
    assert [r["lot_number"] for r in resale] == ["1", "3"]

    first = (Path("data/categorized/auction_77_categorized.json").read_bytes(),
             Path("data/categorized/auction_77_resale.json").read_bytes())
    delta.merge("77", run_tools=False)
    assert (Path("data/categorized/auction_77_categorized.json").read_bytes(),
            Path("data/categorized/auction_77_resale.json").read_bytes()) == first


def test_merge_requires_every_deltas_flags(judged):
    Path("data/categorized/auction_77_d1_flags.json").unlink()
    with pytest.raises(SystemExit, match="d1_flags"):
        delta.merge("77", run_tools=False)


def test_merge_rejects_a_flag_row_the_delta_never_judged(judged):
    _write(Path("data/categorized/auction_77_d1_flags.json"), [_flag(3), _flag(1)])
    with pytest.raises(SystemExit, match="never in"):
        delta.merge("77", run_tools=False)
