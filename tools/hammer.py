"""
Pull what a closed Encore auction's lots actually HAMMERED at.

    python3 tools/hammer.py <ID> [--out data/hammer]
    python3 tools/hammer.py backfill <ID> [<ID> ...] [--out data/hammer]

Writes data/hammer/<close_date>_<ID>.json — one row per PRODUCT, aggregated,
never per lot. `build/hammer.py` joins those files onto a later week's lots so
a repeat product shows what the same thing sold for last time.

This is a side-channel, not a pipeline step. It reads nothing the weekly run
writes and writes nothing the weekly run reads. Run it in step 0 of the
FOLLOWING week's run, when last week's auction is guaranteed closed.

How the price is derived (measured 2026-09-14 — do not re-derive)
----------------------------------------------------------------
`lotSearch(...).results[].bidList` is the bid-increment ladder, and after close
it still starts at the next valid bid ABOVE the final price. So:

    final_price = bidList[0] - (bidList[1] - bidList[0])

Checked against `bidHistory` on 25 random closed lots: 23 exact, 0 mismatches,
2 zero-bid lots. A lot nobody bid on has a ladder starting at the opening bid
([1.0, 2.0, 3.0, ...]), so the formula yields 0 — that is UNSOLD, never "$0".
A ladder shorter than two entries is unsold too.

The obvious-looking fields are all useless here: `lotState.highBid`,
`lotState.bidCount` and `lotState.priceRealized` every one return 0 on every
lot once the auction closes. `bidHistory(input: "<lot id>")` is authoritative
but costs one request PER LOT (28,000 an auction) and carries real bidder
usernames — use it for a spot check, never in this path, and never ship it.

Refusing an open auction
------------------------
Mid-week the ladder's head is the NEXT bid on a live lot, so the formula would
record a mid-week price as a hammer. Every lot must report `status: CLOSED` or
this exits non-zero and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:  # `python3 tools/hammer.py` and `python3 -m tools.hammer` both work
    from scraper import client
    from scraper.condition import parse_condition
    from scraper.parser import _parse_close_at
except ImportError:  # pragma: no cover - only when run without the package
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scraper import client
    from scraper.condition import parse_condition
    from scraper.parser import _parse_close_at


# ---------------------------------------------------------------------------
# The query
# ---------------------------------------------------------------------------
# Deliberately NOT scraper.client.LOT_SEARCH_QUERY. That document defines the
# shape of data/raw/auction_<ID>.json, which scraper/__main__.py's `first_seen`
# carry-forward reads, so it must stay exactly as it is. This one drops the
# pictures and categories (nothing here needs them) and adds `bidList`, which
# costs no extra requests — the whole auction is ~56 pages of 500.

HAMMER_LOT_QUERY = """
query LotSearchHammer($auctionId: Int!, $pageNumber: Int!, $pageLength: Int!) {
  lotSearch(
    input: {auctionId: $auctionId, status: ALL, sortOrder: SALE_ORDER}
    pageLength: $pageLength
    pageNumber: $pageNumber
  ) {
    pagedResults {
      pageLength
      pageNumber
      totalCount
      filteredCount
      results {
        id
        lotNumber
        lead
        description
        bidList
        lotState { status timeLeftTitle }
      }
    }
  }
}
""".strip()

DEFAULT_OUT_DIR = Path("data/hammer")

# Seconds between auctions in a backfill, so a dozen pulls back to back stay
# as polite as the scraper's own per-page pause.
BACKFILL_PAUSE = 2.0

# Closed Encore auctions this repo has run against. 776904 is deliberately
# absent — it is the current week and still open.
KNOWN_CLOSED_AUCTIONS: tuple[int, ...] = (
    741675, 745313, 749101, 763293, 764522, 764523, 764524,
    764528, 764529, 764530, 764604, 774972,
)

# Directories this tool must never write into, whatever --out says. Both hold
# files the weekly build reads by path; a stray file at one of those paths is
# the worst failure mode in this pipeline (see CLAUDE.md).
FORBIDDEN_OUT_DIRS = ("data/raw", "data/categorized")


class NotClosed(RuntimeError):
    """The auction still has open lots — pulling it would record live bids."""


class NoLots(RuntimeError):
    """The auction returned no lots at all."""


# ---------------------------------------------------------------------------
# Price derivation
# ---------------------------------------------------------------------------


def final_price(bid_list: Any) -> float | None:
    """
    The hammer price implied by a closed lot's bid ladder, or None if unsold.

    ``bidList[0]`` is the next valid bid above the final price and the
    increment is constant within a lot, so the final price is one increment
    below the head. Only the first two entries are read — a ladder that widens
    further up (HiBid steps the increment at higher prices) is still correct at
    the bottom, which is where the last real bid sat.

    Returns None — meaning UNSOLD, never 0 — when the ladder is missing, has
    fewer than two entries, or implies a non-positive price (a lot nobody bid
    on opens its ladder at the opening bid).
    """
    if not isinstance(bid_list, (list, tuple)) or len(bid_list) < 2:
        return None
    try:
        head = float(bid_list[0])
        second = float(bid_list[1])
    except (TypeError, ValueError):
        return None
    increment = second - head
    if increment <= 0:
        return None
    final = head - increment
    return final if final > 0 else None


# ---------------------------------------------------------------------------
# Product identity
# ---------------------------------------------------------------------------


def product_key(title: str | None, condition: str | None) -> tuple[str, str]:
    """
    The join key: (TITLE, CONDITION), both stripped and upper-cased.

    `lot_number` and HiBid's `id` are per-listing and recycle week to week
    (93.9% lot_number overlap measured), so neither can join across weeks.
    This is the same grouping `tools/slim_resale.py:group_key` uses — its other
    fields have all been empty since HiBid's 2026-08-30 change — and
    `build/hammer.py` rebuilds it from the merged lot's own title/condition.
    """
    return ((title or "").strip().upper(), (condition or "").strip().upper())


def lot_condition(description: str | None) -> str | None:
    """HiBid's grading for a lot, via the scraper's own parser."""
    condition, _ = parse_condition(description)
    return condition


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def check_closed(results: Iterable[dict[str, Any]]) -> None:
    """Raise NotClosed unless every lot reports status CLOSED."""
    statuses = Counter(
        str(((lot.get("lotState") or {}).get("status") or "")).strip().upper()
        for lot in results
    )
    open_statuses = {s: n for s, n in statuses.items() if s != "CLOSED"}
    if open_statuses:
        detail = ", ".join(
            f"{name or '<none>'}: {count}"
            for name, count in sorted(open_statuses.items(), key=lambda kv: -kv[1])
        )
        raise NotClosed(
            f"{sum(open_statuses.values())} lot(s) are not CLOSED ({detail}). "
            "Pulling a live auction would record mid-week bids as hammer "
            "prices — wait until the auction has finished."
        )


# HiBid blanks every lot's `timeLeftTitle` a few days after close — on
# 2026-09-14 auction 774972's lots still read "Internet Bidding closed at:
# 9/13/2026 1:00:02 PM EST"; by 2026-09-16 every one was "". The auction object
# keeps its dates, so that is the source and the per-lot strings are only a
# fallback. Measured 2026-09-16: bidCloseDateTime is populated for every known
# auction back to 741675 (May) and for the still-open week.
AUCTION_CLOSE_QUERY = """
query AuctionClose($id: Int!) {
  auction(id: $id) { id bidCloseDateTime eventDateEnd }
}
""".strip()


def fetch_close_date(auction_id: int) -> str | None:
    """
    The auction's close date from HiBid's auction object, as YYYY-MM-DD, or
    None if the lookup fails for any reason (the caller falls back).
    """
    try:
        with client._make_session() as session:
            resp = client._post_with_retry(
                session, client.GRAPHQL_URL, label=f"auction-close {auction_id}",
                json={"operationName": "AuctionClose",
                      "variables": {"id": auction_id},
                      "query": AUCTION_CLOSE_QUERY},
                timeout=client.REQUEST_TIMEOUT,
            )
        if not client._is_valid_graphql(resp):
            return None
        auction = (resp.json().get("data") or {}).get("auction") or {}
        for field in ("bidCloseDateTime", "eventDateEnd"):
            value = auction.get(field)
            if isinstance(value, str) and len(value) >= 10:
                return value[:10]
    except Exception:
        return None
    return None


def derive_close_date(results: Iterable[dict[str, Any]],
                      auction_close: str | None = None) -> str:
    """
    The auction's close date, as YYYY-MM-DD.

    Prefers ``auction_close`` (from fetch_close_date). Otherwise the LATEST
    close time across lots — an Encore auction closes in waves over an
    afternoon, and the last wave is the day it ended — which only works for a
    few days after close before HiBid blanks the strings. Falls back to today
    when nothing parses; the file still names its auction id, so a wrong date
    costs ordering, not identity.
    """
    if auction_close:
        return auction_close
    latest: str | None = None
    for lot in results:
        close_at = _parse_close_at((lot.get("lotState") or {}).get("timeLeftTitle"))
        if close_at and (latest is None or close_at > latest):
            latest = close_at
    if latest is None:
        return date.today().isoformat()
    return latest[:10]


def aggregate(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Collapse lots to one row per product.

    `prices` is the sorted list of SOLD finals only, kept so a later
    re-aggregation needs no re-pull; median/low/high are over it. A product
    that sold nothing is still emitted with null figures — "listed 12×, sold 0"
    is information, and dropping it would make an unsold product look like one
    that never ran.
    """
    titles: dict[tuple[str, str], tuple[str, str | None]] = {}
    prices: dict[tuple[str, str], list[float]] = defaultdict(list)
    unsold: Counter[tuple[str, str]] = Counter()

    for lot in results:
        title = (lot.get("lead") or "").strip()
        condition = lot_condition(lot.get("description"))
        key = product_key(title, condition)
        # First lot seen wins the display casing, so re-running is stable.
        titles.setdefault(key, (title, condition))
        price = final_price(lot.get("bidList"))
        if price is None:
            unsold[key] += 1
        else:
            prices[key].append(price)

    products: list[dict[str, Any]] = []
    for key in sorted(titles):
        title, condition = titles[key]
        sold = sorted(prices.get(key, []))
        products.append(
            {
                "title": title,
                "condition": condition,
                "sold": len(sold),
                "unsold": unsold.get(key, 0),
                "median": statistics.median(sold) if sold else None,
                "low": sold[0] if sold else None,
                "high": sold[-1] if sold else None,
                "prices": sold,
            }
        )
    return products


def build_payload(
    auction_id: int, auction_name: str, results: list[dict[str, Any]],
    auction_close: str | None = None,
) -> dict[str, Any]:
    """The whole output file, as a dict."""
    return {
        "auction_id": auction_id,
        "auction_name": auction_name,
        "close_date": derive_close_date(results, auction_close),
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "lots_seen": len(results),
        "products": aggregate(results),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def check_out_dir(out_dir: Path) -> None:
    """Refuse an --out that points anywhere the weekly build reads."""
    resolved = out_dir.resolve()
    for forbidden in FORBIDDEN_OUT_DIRS:
        target = Path(forbidden).resolve()
        if resolved == target or target in resolved.parents:
            raise SystemExit(
                f"Error: refusing to write hammer data under {forbidden}/ — "
                "the weekly build reads that directory by path. Use "
                f"--out {DEFAULT_OUT_DIR} (the default)."
            )


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON via a temp file + os.replace, so a killed run leaves no stub."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def summarise(payload: dict[str, Any], path: Path) -> str:
    """The per-auction report printed after a pull."""
    products = payload["products"]
    sold = sum(p["sold"] for p in products)
    unsold = sum(p["unsold"] for p in products)
    lines = [
        f"Auction {payload['auction_id']} — {payload['auction_name']}",
        f"  closed {payload['close_date']}, {payload['lots_seen']} lots seen",
        f"  {len(products)} distinct products; {sold} sold, {unsold} unsold",
    ]
    top = sorted(products, key=lambda p: (-p["sold"], p["title"]))[:5]
    if top and top[0]["sold"]:
        lines.append("  most-repeated sellers:")
        for p in top:
            if not p["sold"]:
                continue
            lines.append(
                f"    {p['sold']:>3}× median ${p['median']:,.0f} "
                f"(${p['low']:,.0f}–${p['high']:,.0f})  {p['title'][:52]}"
            )
    lines.append(f"  wrote {path}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------


def pull(auction_id: int, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    """
    Fetch, aggregate and write one closed auction.

    Raises NoLots or NotClosed rather than writing anything.
    """
    auction_name, results = client.fetch_all_lots(auction_id, HAMMER_LOT_QUERY)
    if not results:
        raise NoLots(f"auction {auction_id} returned no lots")
    check_closed(results)
    payload = build_payload(auction_id, auction_name, results,
                            fetch_close_date(auction_id))
    path = out_dir / f"{payload['close_date']}_{auction_id}.json"
    write_atomic(path, payload)
    return path, payload


def run(auction_ids: list[int], out_dir: Path, backfill: bool) -> int:
    """Pull each auction. Returns the process exit code."""
    check_out_dir(out_dir)
    failures = 0
    for i, auction_id in enumerate(auction_ids):
        if i:
            time.sleep(BACKFILL_PAUSE)
        try:
            path, payload = pull(auction_id, out_dir)
        except (NoLots, NotClosed) as exc:
            # In a backfill a skip is expected — some of the known ids are the
            # Monday half of a two-auction week, or never ran.
            print(f"Skipped auction {auction_id}: {exc}", file=sys.stderr)
            if not backfill:
                failures += 1
            continue
        except RuntimeError as exc:
            print(f"Failed auction {auction_id}: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(summarise(payload, path))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 tools/hammer.py",
        description=(
            "Pull per-product hammer prices from a CLOSED Encore auction. "
            "Run it in step 0 of the following week's run."
        ),
    )
    parser.add_argument(
        "auction_ids",
        nargs="+",
        metavar="ID",
        help=(
            "Auction id(s). Pass `backfill` as the first argument to pull "
            "several in a row, pausing between them; `backfill` with no ids "
            f"uses the known-closed list ({len(KNOWN_CLOSED_AUCTIONS)} auctions)."
        ),
    )
    parser.add_argument(
        "--out",
        metavar="DIR",
        default=str(DEFAULT_OUT_DIR),
        help=(
            f"Output directory (default {DEFAULT_OUT_DIR}). A flag rather than "
            "a constant so where this lands can change without touching "
            "anything else."
        ),
    )
    args = parser.parse_args(argv)

    ids = list(args.auction_ids)
    backfill = ids and ids[0].lower() == "backfill"
    if backfill:
        ids = ids[1:] or [str(a) for a in KNOWN_CLOSED_AUCTIONS]
    try:
        auction_ids = [int(a) for a in ids]
    except ValueError:
        parser.error(f"auction ids must be integers, got: {' '.join(ids)}")

    return run(auction_ids, Path(args.out), backfill=backfill)


if __name__ == "__main__":
    raise SystemExit(main())
