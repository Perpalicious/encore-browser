"""build/scrapes.py — clustering first_seen timestamps into numbered scrapes."""

from build.schema import Lot
from build.scrapes import assign_scrapes, cluster_first_seen, describe, scrape_labels
from datetime import datetime


def _lot(n: int, first_seen: str | None) -> Lot:
    return Lot(
        day="", lot_number=str(n), title="t", description="", condition=None,
        thumb_url="", image_url="", lot_url="", category="", subcategory="",
        category_path=[], is_bat=False, bat_buckets=[], confidence="low",
        first_seen=first_seen,
    )


SUN = "2026-09-13T21:00:00+00:00"          # Sun Sep 13, 17:00 ET
SUN_LATER = "2026-09-13T21:12:00+00:00"    # the Monday auction, 12 min later
TUE = "2026-09-16T01:30:00+00:00"          # Tue Sep 15, 21:30 ET (Wed in UTC)
THU = "2026-09-17T22:00:00+00:00"          # Thu Sep 17


def test_single_cluster():
    assert cluster_first_seen([SUN, SUN]) == [[SUN]]


def test_runs_minutes_apart_are_one_scrape():
    assert cluster_first_seen([SUN_LATER, SUN]) == [[SUN, SUN_LATER]]


def test_three_days_are_three_scrapes_in_order():
    assert cluster_first_seen([THU, SUN, TUE]) == [[SUN], [TUE], [THU]]


def test_unparseable_is_ignored():
    assert cluster_first_seen(["garbage", SUN, ""]) == [[SUN]]


def test_labels_use_eastern_date_and_disambiguate_same_day():
    starts = [datetime.fromisoformat(SUN), datetime.fromisoformat(TUE)]
    assert scrape_labels(starts) == ["Sun Sep 13", "Tue Sep 15"]
    same_day = [datetime.fromisoformat(SUN), datetime.fromisoformat("2026-09-14T02:00:00+00:00")]
    assert scrape_labels(same_day) == ["Sun Sep 13 17:00", "Sun Sep 13 22:00"]


def test_assign_scrapes_numbers_lots_and_counts():
    lots = [_lot(1, SUN), _lot(2, SUN_LATER), _lot(3, TUE), _lot(4, None), _lot(5, THU)]
    scrapes = assign_scrapes(lots)
    assert [l.scrape for l in lots] == [1, 1, 2, None, 3]
    assert scrapes == [
        {"scrape": 1, "at": SUN, "label": "Sun Sep 13", "count": 2},
        {"scrape": 2, "at": TUE, "label": "Tue Sep 15", "count": 1},
        {"scrape": 3, "at": THU, "label": "Thu Sep 17", "count": 1},
    ]
    assert describe(scrapes).startswith("Scrapes: 3 — Sun Sep 13 (2)")


def test_no_first_seen_means_no_scrapes():
    lots = [_lot(1, None)]
    assert assign_scrapes(lots) == []
    assert lots[0].scrape is None
    assert "none" in describe([])
