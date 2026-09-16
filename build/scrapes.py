"""
Turn per-lot ``first_seen`` timestamps into the numbered scrapes the viewer
can filter on.

An auction grows during the week, and the scraper (``scraper/__main__.py``)
stamps every lot with the run that first saw it. Runs are clustered here: two
timestamps within ``SCRAPE_GAP`` of the cluster's start belong to the same
scrape, so the two auctions of a Sun/Mon week — scraped minutes apart — read as
one scrape, while a Tuesday and a Thursday re-scrape read as two.

Labels are rendered in Eastern time. ``first_seen`` is UTC, and a Sunday
evening scrape is already Monday in UTC; the label should say what the user
remembers doing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from scraper.parser import _TZ_EASTERN

from .schema import Lot

SCRAPE_GAP = timedelta(hours=3)


def _parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None
    return dt if dt.tzinfo is not None else None


def cluster_first_seen(values: Iterable[str]) -> list[list[str]]:
    """Group distinct timestamps into runs; each cluster is sorted ascending
    and the outer list is ordered by cluster start. Unparseable values are
    ignored, exactly like a missing ``first_seen``."""
    parsed = sorted(
        {(dt, v) for v in set(values) if (dt := _parse(v)) is not None}
    )
    clusters: list[list[str]] = []
    start: datetime | None = None
    for dt, value in parsed:
        if start is None or dt - start > SCRAPE_GAP:
            clusters.append([value])
            start = dt
        else:
            clusters[-1].append(value)
    return clusters


def scrape_labels(starts: list[datetime]) -> list[str]:
    """``"Tue Sep 15"`` per cluster start, in Eastern time; when two clusters
    fall on the same day the time is appended so they stay distinguishable."""
    local = [dt.astimezone(_TZ_EASTERN) for dt in starts]
    days = [f"{dt:%a %b} {dt.day}" for dt in local]
    return [
        f"{day} {dt:%H:%M}" if days.count(day) > 1 else day
        for day, dt in zip(days, local)
    ]


def assign_scrapes(lots: list[Lot]) -> list[dict[str, Any]]:
    """Set ``lot.scrape`` in place (1-based; None when the lot has no usable
    ``first_seen``) and return the envelope entries, one per scrape:
    ``{"scrape", "at", "label", "count"}``. Empty when nothing carries
    ``first_seen`` — the viewer hides the control then."""
    clusters = cluster_first_seen(l.first_seen for l in lots if l.first_seen)
    index_of = {v: i for i, cluster in enumerate(clusters, 1) for v in cluster}
    counts = [0] * len(clusters)
    for lot in lots:
        idx = index_of.get(lot.first_seen or "")
        lot.scrape = idx
        if idx is not None:
            counts[idx - 1] += 1
    labels = scrape_labels([_parse(c[0]) for c in clusters])  # type: ignore[misc]
    return [
        {"scrape": i, "at": cluster[0], "label": label, "count": count}
        for i, (cluster, label, count) in enumerate(zip(clusters, labels, counts), 1)
    ]


def describe(scrapes: list[dict[str, Any]]) -> str:
    if not scrapes:
        return "Scrapes: none (raw carries no first_seen)"
    parts = " · ".join(f"{s['label']} ({s['count']:,})" for s in scrapes)
    return f"Scrapes: {len(scrapes)} — {parts}"
