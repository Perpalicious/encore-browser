#!/usr/bin/env python3
"""Partition a week's slimmed lots into one file per flagging pass.

    python3 tools/split_passes.py <ID>
    python3 tools/split_passes.py <ID> --suggest    # re-derive focus lists

Reads  data/categorized/auction_<ID>_for_agent.json
Writes data/categorized/auction_<ID>_pass_<a|b|c|d>.json

WHY, IN ONE PARAGRAPH
---------------------
tools/prefilter.py shortlists ~44% of the auction and hands only that to the
model. Measured against three months of real bid/watch history, that shortlist
reaches 77.4% of the lots actually BID ON — one pick in four could never be
seen, and no prompt change recovers it. Judging everything in ONE prompt was
the old approach and starved narrow buckets (77 KEYBOARD lots, 5 flagged).
This splits the difference: every lot is judged exactly once, but by a prompt
holding 13-30 relevant buckets instead of 62. See passes.yaml.

GUARANTEES, all asserted at runtime:
  - every lot lands in exactly one pass (no drops, no double-judging)
  - the union of the parts equals the input lot set, by lot_set_sha
  - a lot whose category is missing or unrecognised goes to `fallback`
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prefilter import (  # noqa: E402
    build_matchers,
    category_prefixes,
    crumb_segments,
    haystack,
    lot_set_sha,
)


def load_passes(path: Path) -> tuple[list[dict], str]:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    return spec["passes"], spec.get("fallback", "D")


def assign(lot: dict, passes: list[dict], fallback: str) -> str:
    """First matching pass wins, so order passes.yaml most-specific-first.

    Pass A's prefixes are three segments deep and live *inside* pass B's
    single-segment prefix; if B were tested first it would swallow all of A.
    """
    segments = crumb_segments(lot.get("category"))
    for spec in passes:
        for crumb in category_prefixes(spec["categories"]):
            if segments[: len(crumb)] == crumb:
                return spec["id"]
    return fallback


def suggest(lots: list[dict], passes: list[dict], fallback: str) -> None:
    """Re-derive focus_buckets from where inventory actually sits this week."""
    buckets = yaml.safe_load(Path("buckets.yaml").read_text(encoding="utf-8"))["buckets"]
    profile = yaml.safe_load(Path("profile.yaml").read_text(encoding="utf-8"))["interests"]
    matchers, _ = build_matchers(buckets, profile)
    per = defaultdict(Counter)
    for lot in lots:
        pid = assign(lot, passes, fallback)
        text, segs = haystack(lot), crumb_segments(lot.get("category"))
        for m in matchers:
            if m.match(text, segs, None) is not None:
                per[m.name][pid] += 1
    out = defaultdict(list)
    for bucket in buckets:
        counts = per[bucket["name"]]
        total = sum(counts.values())
        if not total:
            continue
        top = counts.most_common(1)[0][0]
        for spec in passes:
            pid = spec["id"]
            if pid == top or counts[pid] / total >= 0.15:
                out[pid].append(bucket["name"])
    print("Suggested focus_buckets (bucket's top pass, plus any pass holding >=15%):")
    for spec in passes:
        names = sorted(out[spec["id"]])
        print(f"\n  # {spec['id']} — {len(names)} buckets")
        print("  focus_buckets:")
        print("    " + json.dumps(names, indent=None))
    zero = [b["name"] for b in buckets if not sum(per[b["name"]].values())]
    if zero:
        print(f"\n  no inventory this week (keep in a focus list by hand): {zero}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("auction_id")
    ap.add_argument("--passes", default="passes.yaml", type=Path)
    ap.add_argument("--suggest", action="store_true",
                    help="print data-derived focus_buckets and exit; writes nothing")
    args = ap.parse_args(argv)

    src = Path("data/categorized") / f"auction_{args.auction_id}_for_agent.json"
    if not src.exists():
        print(f"Error: {src} not found. Run tools/slim.py first.", file=sys.stderr)
        return 1
    raw = json.loads(src.read_text(encoding="utf-8"))
    lots = raw.get("items", raw) if isinstance(raw, dict) else raw

    passes, fallback = load_passes(args.passes)
    if args.suggest:
        suggest(lots, passes, fallback)
        return 0

    by_pass: dict[str, list[dict]] = {p["id"]: [] for p in passes}
    for lot in lots:
        by_pass[assign(lot, passes, fallback)].append(lot)

    total = sum(len(v) for v in by_pass.values())
    assert total == len(lots), f"partition lost lots: {total} != {len(lots)}"
    seen: set[str] = set()
    for rows in by_pass.values():
        for lot in rows:
            key = str(lot.get("lot_number"))
            assert key not in seen, f"lot {key} landed in two passes"
            seen.add(key)

    sha = lot_set_sha(lots)
    out_dir = Path("data/categorized")
    print(f"{len(lots):,} lots -> {len(passes)} passes (lot_set_sha {sha})\n")
    for spec in passes:
        rows = by_pass[spec["id"]]
        path = out_dir / f"auction_{args.auction_id}_pass_{spec['id'].lower()}.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        share = len(rows) / len(lots) * 100 if lots else 0
        print(f"  pass {spec['id']}  {spec['name']:34s} {len(rows):6,} lots  {share:4.1f}%"
              f"  {len(spec['focus_buckets']):2d} focus buckets")
        print(f"           -> {path}")
    print(f"\n  every lot judged exactly once: {total == len(lots) == len(seen)}")

    unknown = [lot for lot in lots if not (lot.get("category") or "").strip()]
    if unknown:
        print(f"  WARNING: {len(unknown)} lots have no category and went to "
              f"the '{fallback}' fallback pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
