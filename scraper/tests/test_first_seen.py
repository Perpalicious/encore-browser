"""first_seen stamping: a re-scrape keeps the run that first saw each lot."""

import json
from pathlib import Path

from scraper.__main__ import load_prior_first_seen, stamp_first_seen

T1 = "2026-09-13T21:00:00+00:00"
T2 = "2026-09-15T22:30:00+00:00"


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_no_prior_file_stamps_everything_with_this_run(tmp_path):
    items = [{"id": 1, "lot_number": "10"}, {"id": 2, "lot_number": "11"}]
    prior = load_prior_first_seen(tmp_path / "missing.json")
    assert prior == {}
    assert stamp_first_seen(items, prior, T1) == 2
    assert all(i["first_seen"] == T1 for i in items)


def test_prior_first_seen_is_carried_and_new_ids_get_this_run(tmp_path):
    path = tmp_path / "raw.json"
    _write(path, {"scraped_at": T1, "items": [{"id": 1, "lot_number": "10", "first_seen": T1}]})
    items = [{"id": 1, "lot_number": "10"}, {"id": 2, "lot_number": "11"}]
    assert stamp_first_seen(items, load_prior_first_seen(path), T2) == 1
    assert items[0]["first_seen"] == T1
    assert items[1]["first_seen"] == T2


def test_prior_without_first_seen_falls_back_to_its_scraped_at(tmp_path):
    path = tmp_path / "raw.json"
    _write(path, {"scraped_at": T1, "items": [{"id": 1, "lot_number": "10"}]})
    assert load_prior_first_seen(path) == {"1": T1}


def test_match_is_on_id_so_prefixed_lot_numbers_survive(tmp_path):
    path = tmp_path / "raw.json"
    _write(path, {"scraped_at": T1, "items": [{"id": 7, "lot_number": "S-10", "first_seen": T1}]})
    items = [{"id": 7, "lot_number": "10"}]
    assert stamp_first_seen(items, load_prior_first_seen(path), T2) == 0
    assert items[0]["first_seen"] == T1


def test_bare_list_or_garbage_is_a_first_scrape(tmp_path):
    path = tmp_path / "raw.json"
    _write(path, [{"id": 1}])
    assert load_prior_first_seen(path) == {}
    path.write_text("{not json", encoding="utf-8")
    assert load_prior_first_seen(path) == {}
