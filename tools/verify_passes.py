"""
Verify the ChatGPT pass outputs before anything is merged or built.

    python3 tools/verify_passes.py <ID>

Checks each file for required fields, structural invariants, and — the
important part — that its lot_numbers match this week's slimmed file exactly.

Why the lot-set check matters
-----------------------------
Two-auction weeks all write to `auction_combined_*.json`, so last week's files
sit at exactly the paths this week's build reads. Measured on real data, a
previous week's categorized file shared 93.9% of its lot_numbers with the
following week's auction — because the S-/M- prefixes and lot numbering repeat.

Building against a stale file therefore does not fail. It joins last week's
flags onto this week's different items at the same lot numbers and produces a
complete, plausible, entirely wrong bundle. Row counts alone do not catch it;
comparing the actual lot sets does. `tools/prefilter.py` additionally stamps a
`lot_set_sha` into the base file, which `merge_categorized` carries into the
categorized file — checked below as a second, exact tripwire.

Why the gates below are FAILs and not reports
---------------------------------------------
The 2026-08-15 run shipped `bats_subtype` on 0 of 27,440 lots. This script
printed "no bats_subtype at all" and exited 0, the bundle built cleanly, and
the viewer's third drill-down level was dead for a week before anyone noticed.
Everything here that can silently produce a wrong-but-plausible bundle now
fails the run instead of reporting into a scroll-back.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import yaml

# One merged pass emits both the bucket flags and the personal fields.
# Imported rather than restated so the validator that accepts a row at ingest
# time and the gate that accepts the merged file cannot disagree about what a
# required field is.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from classify.contract import REQUIRED_FIELDS as REQUIRED  # noqa: E402

# Below this share of flagged lots carrying a subtype, the drill-down's third
# level is too sparse to navigate and the pass almost certainly ignored the
# instruction rather than judging each lot unnameable.
SUBTYPE_MIN_PCT = 90
# A pick with no explanation is unreviewable in the detail panel.
REASONING_MIN_PCT = 95


def load(path: Path) -> tuple[list[dict], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"], {k: v for k, v in data.items() if k != "items"}
    if isinstance(data, list):
        return data, {}
    raise ValueError("expected a JSON array or an object with an 'items' array")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check_categorized(
    items: list[dict], buckets: list[dict], profile: dict
) -> tuple[list[str], list[str]]:
    """Structural gates specific to the merged flagging + personal pass.

    Returns (problems, info) rather than printing, so the caller can emit the
    FAIL/ok status line before the detail lines that explain it.
    """
    problems: list[str] = []
    info: list[str] = []
    bucket_names = {b["name"] for b in buckets}

    # `build/transform.py` detects "Shape B" purely by the presence of a
    # `bats_category` key, and Shape B ignores `bats_buckets` completely — so a
    # single stray key silently empties every lot's buckets.
    if any("bats_category" in r for r in items):
        n = sum(1 for r in items if "bats_category" in r)
        problems.append(
            f"{n} rows carry a `bats_category` key. build/transform.py would "
            f"switch to Shape B and ignore `bats_buckets` entirely."
        )

    unknown_buckets = Counter()
    invariant_violations = 0
    for row in items:
        listed = row.get("bats_buckets") or []
        for name in listed:
            if name not in bucket_names:
                unknown_buckets[name] += 1
        if bool(row.get("is_bats_list")) != bool(listed):
            invariant_violations += 1

    if unknown_buckets:
        worst = ", ".join(f"{n!r} ({c})" for n, c in unknown_buckets.most_common(5))
        problems.append(
            f"{len(unknown_buckets)} bucket names are not in buckets.yaml and would "
            f"fall into the synthetic \"Other\" group: {worst}"
        )
    if invariant_violations:
        problems.append(
            f"{invariant_violations} rows break `is_bats_list == (bats_buckets "
            f"is non-empty)`. Those lots appear on the Bat tab under no bucket, "
            f"or carry buckets while filtered out of it."
        )

    flagged = [r for r in items if r.get("bats_buckets")]
    if flagged:
        with_subtype = [r for r in flagged if r.get("bats_subtype")]
        pct = 100 * len(with_subtype) / len(flagged)
        subtypes = [" ".join(str(r["bats_subtype"]).split()).lower() for r in with_subtype]
        distinct = len(set(subtypes))
        info.append(f"subtypes: {len(with_subtype)}/{len(flagged)} flagged lots "
                    f"({pct:.0f}%), {distinct} distinct")
        if pct < SUBTYPE_MIN_PCT:
            problems.append(
                f"only {pct:.0f}% of flagged lots carry `bats_subtype` "
                f"(need {SUBTYPE_MIN_PCT}%). The drill-down's third level needs it; "
                f"the 2026-08-15 run shipped 0% and nobody noticed for a week."
            )
        elif distinct > max(40, len(subtypes) // 4):
            info.append(f"{distinct} distinct subtypes for {len(subtypes)} lots reads as "
                        f"per-lot phrasing rather than reused wording")

        declared = {
            " ".join(str(s).split()).lower()
            for b in buckets
            for s in (b.get("subtypes") or [])
        }
        stray = Counter(s for s in subtypes if s not in declared)
        if stray:
            top = ", ".join(f"{s!r}({c})" for s, c in stray.most_common(5))
            info.append(f"{len(stray)} subtypes outside any bucket's declared "
                        f"vocabulary: {top}")

    picks = [r for r in items if r.get("personal_match") is True]
    info.append(f"personal picks: {len(picks)}/{len(items)} "
                f"({100 * len(picks) / len(items):.1f}%)")
    if picks:
        explained = sum(1 for r in picks if r.get("personal_reasoning"))
        pct = 100 * explained / len(picks)
        if pct < REASONING_MIN_PCT:
            problems.append(
                f"only {pct:.0f}% of personal picks carry `personal_reasoning` "
                f"(need {REASONING_MIN_PCT}%). Note the merged pass must emit that "
                f"exact key — `reasoning` is silently dropped by build/transform.py."
            )
        vocab = {
            str(t).lower()
            for i in (profile.get("interests") or [])
            for t in (i.get("tags") or [])
        }
        if vocab:
            stray = Counter(
                str(t).lower()
                for r in picks
                for t in (r.get("personal_tags") or [])
                if str(t).lower() not in vocab
            )
            if stray:
                top = ", ".join(f"{s!r}({c})" for s, c in stray.most_common(5))
                info.append(f"{len(stray)} personal_tags outside profile.yaml's "
                            f"vocabulary: {top}")
    return problems, info


def report_bucket_recall(auction_id: str, items: list[dict], buckets: list[dict],
                         profile: dict) -> None:
    """What the model was shown per bucket vs what it kept.

    Two shapes matter. A bucket shown ≥20 candidates and keeping none means the
    model refused the whole bucket — exactly the failure this pipeline exists to
    fix. A bucket keeping >95% means the shortlist is doing the judging, so the
    seeds have become a whitelist and the `description` is no longer deciding.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from prefilter import Matcher, build_matchers, load_items, shortlist
    except ImportError:
        return

    slim_path = Path(f"data/categorized/auction_{auction_id}_for_agent.json")
    if not slim_path.exists():
        return
    lots = load_items(slim_path, "slimmed file")
    bucket_matchers, pseudo = build_matchers(buckets, profile.get("interests") or [])
    cand_by_lot, _, _ = shortlist(lots, bucket_matchers, pseudo)

    shown = Counter(n for names in cand_by_lot.values() for n in names)
    kept = Counter()
    outside = Counter()
    for row in items:
        cands = set(cand_by_lot.get(str(row.get("lot_number")), []))
        for name in row.get("bats_buckets") or []:
            kept[name] += 1
            if name not in cands:
                outside[name] += 1

    print(f"\n{'bucket':45s} {'shown':>7s} {'kept':>7s} {'rate':>7s} {'outside':>8s}")
    for name in sorted(set(shown) | set(kept)):
        s, k, o = shown.get(name, 0), kept.get(name, 0), outside.get(name, 0)
        note = ""
        if s >= 20 and k == 0:
            note = "  <-- refused the whole bucket"
        elif s and k / s > 0.95:
            note = "  <-- shortlist is doing the judging"
        rate = f"{100 * k / s:6.1f}%" if s else "     - "
        print(f"{name:45s} {s:7d} {k:7d} {rate} {o:8d}{note}")

    total_outside = sum(outside.values())
    if total_outside:
        print(f"\n{total_outside} accepted (lot, bucket) pairs were assigned OUTSIDE the "
              f"shortlist.\nThat is the prefilter's own recall gap — feed these back as "
              f"seeds via `tools/prefilter.py <ID> --audit`.")


def main(auction_id: str) -> None:
    slim_path = Path(f"data/categorized/auction_{auction_id}_for_agent.json")
    if not slim_path.exists():
        sys.exit(f"Error: slimmed file not found: {slim_path}")
    slim_items, _ = load(slim_path)
    expected = {str(r["lot_number"]) for r in slim_items}
    print(f"this week's slimmed file: {len(expected)} lots\n")

    buckets = load_yaml(Path("buckets.yaml")).get("buckets") or []
    profile = load_yaml(Path("profile.yaml"))

    failed = False
    categorized_items: list[dict] = []
    for label in ("categorized", "resale"):
        path = Path(f"data/categorized/auction_{auction_id}_{label}.json")
        if not path.exists():
            print(f"{label:12s} MISSING  {path}")
            failed = True
            continue

        try:
            items, envelope = load(path)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"{label:12s} UNREADABLE  {exc}")
            print(f"{'':12s}   (a markdown-wrapped or truncated response looks like this)")
            failed = True
            continue

        if not items:
            print(f"{label:12s} EMPTY")
            failed = True
            continue

        problems = []
        # Union over ALL rows, not row 0. The merged pass omits keys on
        # non-matches, so sampling one row reports whichever lot sorts first.
        fields = set().union(*(set(r.keys()) for r in items))
        missing_fields = REQUIRED[label] - fields
        if missing_fields:
            problems.append(f"missing fields {sorted(missing_fields)}")

        lots = {str(r.get("lot_number")) for r in items}
        dupes = len(items) - len(lots)
        if dupes:
            problems.append(f"{dupes} duplicate lot_numbers")

        unknown = lots - expected
        absent = expected - lots
        if unknown:
            problems.append(
                f"{len(unknown)} lot_numbers not in this week's auction "
                f"(e.g. {sorted(unknown)[:3]}) — likely a stale file"
            )
        # Only the categorized pass strictly must cover every lot: it decides
        # which lots exist in the bundle at all. The others are joins.
        if absent:
            pct = 100 * len(absent) / len(expected)
            note = f"{len(absent)} lots absent ({pct:.1f}%)"
            problems.append(note if label == "categorized"
                            else note + " — expected only if the pass skipped lots")

        hard = bool(unknown or missing_fields or dupes or (absent and label == "categorized"))
        info: list[str] = []

        if label == "categorized":
            categorized_items = items
            # The prefilter stamps this into the base file; merge_categorized
            # preserves the envelope, so it should still be here.
            stamped = envelope.get("lot_set_sha")
            prefilter_path = Path(f"data/categorized/auction_{auction_id}_prefilter.json")
            if stamped and prefilter_path.exists():
                expected_sha = json.loads(
                    prefilter_path.read_text(encoding="utf-8")).get("lot_set_sha")
                if expected_sha and stamped != expected_sha:
                    problems.append(
                        f"lot_set_sha {stamped} does not match this week's prefilter "
                        f"run ({expected_sha}) — this file was built from a different scrape"
                    )
                    hard = True
            elif not stamped:
                info.append("no lot_set_sha — built without tools/prefilter.py")
            cat_problems, cat_info = check_categorized(items, buckets, profile)
            problems.extend(cat_problems)
            info.extend(cat_info)
            hard = hard or bool(problems)

        print(f"{label:12s} {'FAIL' if hard else 'ok  '}  "
              f"{len(items)} rows, {len(lots)} distinct lots")
        if hard:
            failed = True
        for p in problems:
            print(f"{'':12s}   - {p}")
        for i in info:
            print(f"{'':12s}   {i}")

    if categorized_items and buckets:
        report_bucket_recall(auction_id, categorized_items, buckets, profile)

    print()
    if failed:
        sys.exit("VERIFY FAILED — do not build. Fix the files above and re-run.")
    print("Both files verified against this week's lot set.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
