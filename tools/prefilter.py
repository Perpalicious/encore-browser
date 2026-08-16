"""
Shortlist auction lots per bucket so the flagging pass judges a small,
positive-dense candidate set instead of the whole auction.

    python3 tools/prefilter.py <ID>
    python3 tools/prefilter.py <ID> --backtest <prev_categorized.json>
    python3 tools/prefilter.py <ID> --audit <flags.json>

Reads  data/categorized/auction_<ID>_for_agent.json
       buckets.yaml, profile.yaml
Writes data/categorized/auction_<ID>_candidates.json  (the model's input)
       data/categorized/auction_<ID>_base.json        (all-false row per lot)
       data/categorized/auction_<ID>_sweep.json       (non-candidate QA sample)
       data/categorized/auction_<ID>_prefilter.json   (stats + hashes)

Why this exists
---------------
The flagging pass used to be 45-way multi-label classification over ~27k lots
with an ~85% negative rate. Measured on the 2026-08-15 run, the model settled
into a mostly-false prior: only high-frequency patterns broke through (Kitchen
appliances 816, Bedding 501) while narrow buckets starved. 77 lots had
KEYBOARD in title or model and 5 were flagged; one of those 5 was a lawn-mower
IGNITION KEY SWITCH. Of 4,119 flagged lots, 3,951 got exactly one bucket
despite the prompt saying "list all that apply".

Shortlisting first fixes the input distribution rather than nagging the model.
Non-candidates never reach it at all — they get an all-false row from
`_base.json` at zero token cost — and what does reach it arrives grouped by
bucket, one topic at a time.

The tradeoff, stated plainly
----------------------------
This caps the model's recall at whatever the shortlist catches. A seed typo
silently guarantees zero recall for its bucket. Four things keep that honest:

  - `categories:` matches HiBid's breadcrumb, which reaches bare-SKU lots that
    carry no usable keyword at all. Measured: the peripherals breadcrumb holds
    199 lots, only 60 of them keyword-positive.
  - `--backtest` replays the seeds against a previous week's accepted labels
    and reports real per-bucket recall, for free, as often as you like.
  - `--audit` reports what the model accepted OUTSIDE its shortlist, which is
    direct evidence of what the seeds are missing.
  - A bucket that shortlists nothing is a warning, every run.

Seed matching
-------------
Seeds are lowercased substrings anchored at a word boundary on the LEFT only:
`tote` matches "TOTES", `keyboard` matches "KEYBOARDS", and `key` matches
"KEYBOARD" but not "MONKEY". That asymmetry is deliberate — plural and
compound forms are the common case, and a trailing boundary would miss them.

Seeds must be curated. Deriving them from the bucket `description` prose was
prototyped and makes 92% of all lots candidates (Smart home alone: 14,135).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

# Fields concatenated into the text a seed is matched against. `category` is
# included so a breadcrumb word ("Keyboards / Mice") can rescue a bare-SKU
# title, which is the single biggest source of lexically-invisible lots.
HAYSTACK_FIELDS = ("title", "model", "size", "notes", "category")

# HiBid joins breadcrumb segments with this exact string; `build/merge.py`
# splits on it too. Matching on segments rather than raw substrings keeps
# "Computers" from matching "Computers & Electronics - ... - Computer Desks".
CRUMB_SEP = " - "

# Every non-candidate lot gets exactly this row, with lot_number filled in.
# Four keys, matching what PROMPTS.md requires of a non-match: merge_categorized
# replaces whole rows, so a shorter row would drop bats_buckets/personal_match
# and turn personal_match into null in the bundle.
BASE_ROW = {"is_bats_list": False, "bats_buckets": [], "personal_match": False}

DEFAULT_MAX_BUCKET_SHARE = 0.08
# Measured normal is ~8.9k candidates from ~27.4k lots (32%). The cap is a
# runaway-seed tripwire, not a target — set well above normal so a slightly
# bigger auction does not hard-fail a Sunday-night run.
DEFAULT_MAX_ROWS = 12000
DEFAULT_SWEEP = 500
SWEEP_SEED = 20260815


# --------------------------------------------------------------------------
# loading


def load_items(path: Path, label: str) -> list[dict]:
    if not path.exists():
        sys.exit(f"Error: {label} not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    sys.exit(f"Error: {label} must be a JSON array or an object with 'items'.")


def load_yaml(path: Path, label: str) -> dict:
    if not path.exists():
        sys.exit(f"Error: {label} not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def lot_set_sha(items: list[dict]) -> str:
    """Fingerprint of this auction's lot numbers.

    Stamped into `_base.json`'s envelope, which `merge_categorized` preserves
    into the merged categorized file, so `verify_passes.py` can prove the
    file it is checking was built from this week's scrape. Two-auction weeks
    all write to `auction_combined_*`, and a previous week's file overlaps
    ~94% of this week's lot numbers — row counts never catch that.
    """
    joined = "\n".join(sorted(str(i.get("lot_number")) for i in items))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# matching


def compile_seeds(seeds: list[str]) -> re.Pattern | None:
    """Left-anchored alternation over the seed list. See module docstring.

    A seed written with a TRAILING SPACE is anchored on the right as well:
    `"pla "` becomes \\bpla\\b and matches "PLA FILAMENT" but not "PLATED" or
    "PLASTIC". Without it, `pla` shortlisted 581 lots of costume jewellery.
    Use the trailing space on any seed that is a prefix of a common unrelated
    word — `mop `, `toro `, `vans `, `ninja `.
    """
    parts = []
    for seed in seeds:
        if not seed or not seed.strip():
            continue
        anchored = seed != seed.rstrip()
        text = normalise(seed.strip())
        parts.append((text, re.escape(text) + (r"\b" if anchored else "")))
    if not parts:
        return None
    # Longest first so the reported "which seed matched" is the specific one.
    parts.sort(key=lambda p: len(p[0]), reverse=True)
    return re.compile(r"\b(" + "|".join(p[1] for p in parts) + r")")


def crumb_segments(category: str | None) -> list[str]:
    # Split on the separator FIRST — normalise() would flatten the hyphen in
    # " - " and destroy the segment boundaries.
    if not category:
        return []
    return [normalise(seg.strip()) for seg in str(category).split(CRUMB_SEP)]


def category_prefixes(prefixes: list[str]) -> list[list[str]]:
    return [crumb_segments(p) for p in prefixes if p and str(p).strip()]


def normalise(text: str) -> str:
    """Lowercase and flatten hyphens/slashes to spaces.

    Applied to BOTH seeds and lot text, so `pull up bar` matches "PULL-UP BAR"
    and `hot swap` matches "HOT-SWAP". Titles here punctuate the same product
    inconsistently across lots, and without this a seed silently misses every
    hyphenated spelling — which is how "PULL-UP BAR" went unshortlisted.
    """
    return re.sub(r"[-/]+", " ", text.lower())


def haystack(lot: dict) -> str:
    parts = [str(lot.get(f) or "") for f in HAYSTACK_FIELDS]
    return normalise(" ".join(parts))


class Matcher:
    """One bucket's (or pseudo-bucket's) shortlist rule."""

    def __init__(self, name: str, spec: dict):
        self.name = name
        self.seed_re = compile_seeds(spec.get("seeds") or [])
        self.exclude_re = compile_seeds(spec.get("exclude") or [])
        self.crumbs = category_prefixes(spec.get("categories") or [])
        self.seeds = [s.strip().lower() for s in (spec.get("seeds") or []) if s.strip()]

    @property
    def configured(self) -> bool:
        return bool(self.seed_re or self.crumbs)

    def match(self, text: str, segments: list[str]) -> str | None:
        """Return the reason this lot is a candidate, or None."""
        if self.exclude_re and self.exclude_re.search(text):
            return None
        if self.seed_re:
            hit = self.seed_re.search(text)
            if hit:
                return hit.group(1)
        for crumb in self.crumbs:
            if segments[: len(crumb)] == crumb:
                return CRUMB_SEP.join(crumb)
        return None


def build_matchers(buckets: list[dict], interests: list[dict]) -> tuple[list[Matcher], list[Matcher]]:
    """Bucket matchers, and pseudo-bucket matchers from profile interests.

    ANY interest carrying `seeds:` becomes a pseudo-bucket, not just the ones
    with no buckets at all. An interest can be mostly covered by its buckets
    and still have uncovered edges: "Kids' toys" owns Barbies/Lego/Hatchimals
    but no bucket holds a generic doll, and "Garage & workshop" owns Power
    tools but no bucket holds a hand chisel. Measured against the 2026-08-15
    picks, that gap accounted for most of the personal picks the shortlist
    would otherwise have dropped.
    """
    bucket_matchers = [Matcher(b["name"], b) for b in buckets]
    pseudo = [
        Matcher(i["name"], i)
        for i in interests
        if i.get("seeds") or i.get("categories")
    ]
    return bucket_matchers, pseudo


# --------------------------------------------------------------------------
# lint


def lint_profile(buckets: list[dict], interests: list[dict]) -> list[str]:
    """The profile is supposed to justify the taxonomy. Prove it still does."""
    problems = []
    bucket_names = {b["name"] for b in buckets}
    claimed: set[str] = set()
    for interest in interests:
        for name in interest.get("buckets") or []:
            if name not in bucket_names:
                problems.append(
                    f"profile.yaml interest {interest['name']!r} names bucket "
                    f"{name!r}, which is not in buckets.yaml"
                )
            claimed.add(name)
    for name in sorted(bucket_names - claimed):
        problems.append(
            f"bucket {name!r} is claimed by no profile interest — either add it "
            f"to an interest's `buckets:` or drop the bucket"
        )
    return problems


def lint_examples(buckets: list[dict]) -> list[str]:
    """A bucket's own `examples` brands should survive its own shortlist.

    Cheap, self-contained recall check: if a bucket names Keychron as an
    example and its seeds would not shortlist a lot titled "KEYCHRON ...",
    the seeds are wrong and no auction data is needed to know it.

    `seed_exempt:` lists examples deliberately left unseeded because the brand
    word is a common English word or another product's name — "Corona",
    "August", "Level", "Global", "Mac", "Nest". Seeding those would cost far
    more in false candidates than they return. Listing them here records the
    decision instead of leaving a warning that trains the user to ignore
    warnings.
    """
    warnings = []
    for bucket in buckets:
        matcher = Matcher(bucket["name"], bucket)
        if not matcher.configured:
            continue
        exempt = {normalise(str(e)) for e in (bucket.get("seed_exempt") or [])}
        missed = [
            ex
            for ex in (bucket.get("examples") or [])
            if normalise(str(ex)) not in exempt and not matcher.match(normalise(str(ex)), [])
        ]
        if missed:
            warnings.append(
                f"{bucket['name']}: own examples not shortlisted by own seeds: {missed}"
            )
    return warnings


# --------------------------------------------------------------------------
# the main shortlist pass


def shortlist(
    lots: list[dict],
    bucket_matchers: list[Matcher],
    pseudo_matchers: list[Matcher],
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, Counter]]:
    """Returns (cand_by_lot, profile_by_lot, seed_hits_by_bucket)."""
    cand_by_lot: dict[str, list[str]] = {}
    profile_by_lot: dict[str, list[str]] = {}
    seed_hits: dict[str, Counter] = defaultdict(Counter)

    for lot in lots:
        key = str(lot.get("lot_number"))
        text = haystack(lot)
        segments = crumb_segments(lot.get("category"))

        hits = []
        for matcher in bucket_matchers:
            reason = matcher.match(text, segments)
            if reason is not None:
                hits.append(matcher.name)
                seed_hits[matcher.name][reason] += 1
        if hits:
            cand_by_lot[key] = hits

        pseudo_hits = [m.name for m in pseudo_matchers if m.match(text, segments) is not None]
        if pseudo_hits:
            profile_by_lot[key] = pseudo_hits

    return cand_by_lot, profile_by_lot, seed_hits


def candidate_row(lot: dict, cand: list[str], profile: list[str]) -> dict:
    """Same omit-when-absent discipline as tools/slim.py — every key costs
    output budget, and an absent key is itself information."""
    row = {"lot_number": lot.get("lot_number"), "title": lot.get("title", "")}
    for field in ("model", "size", "condition", "category", "notes", "damage",
                  "missing_parts", "damaged", "missing_major_parts", "functional",
                  "est_retail_price"):
        value = lot.get(field)
        if value not in (None, "", []):
            row[field] = value
    if cand:
        row["cand"] = cand
    if profile:
        row["profile"] = profile
    return row


def order_candidates(
    rows: list[dict], bucket_sizes: dict[str, int]
) -> tuple[list[dict], list[tuple[str, int, int]]]:
    """Group each lot under its rarest candidate bucket.

    Contiguity is the point: a one-topic run of rows is what stops the model
    settling back into a mostly-false prior, and rarest-first puts the narrow
    buckets — the ones that failed — at the top of the file where attention is
    freshest. Returns (rows, [(bucket, start_offset, count)]) so CLAUDE.md can
    tell the user where to split pastes.
    """
    def primary(row: dict) -> str:
        cands = row.get("cand") or []
        if not cands:
            return "~profile only"
        return min(cands, key=lambda b: (bucket_sizes.get(b, 0), b))

    for row in rows:
        row["_primary"] = primary(row)

    rows.sort(key=lambda r: (
        bucket_sizes.get(r["_primary"], 0),
        r["_primary"],
        str(r.get("lot_number")),
    ))

    boundaries = []
    current = None
    start = 0
    for idx, row in enumerate(rows):
        if row["_primary"] != current:
            if current is not None:
                boundaries.append((current, start, idx - start))
            current = row["_primary"]
            start = idx
    if current is not None:
        boundaries.append((current, start, len(rows) - start))

    for row in rows:
        del row["_primary"]
    return rows, boundaries


# --------------------------------------------------------------------------
# modes


def run_backtest(
    lots: list[dict],
    bucket_matchers: list[Matcher],
    buckets: list[dict],
    prev_path: Path,
) -> int:
    """Replay the seeds against a previous run's accepted (lot, bucket) pairs.

    This is the recall number, and it costs nothing. A seed edit can be
    re-measured immediately instead of waiting a week to find out it was wrong.
    """
    prev = load_items(prev_path, "previous categorized file")
    # Old bucket names survive here after a rename; `aliases:` maps them
    # forward so a rename doesn't read as a recall collapse.
    alias = {}
    for bucket in buckets:
        for old in bucket.get("aliases") or []:
            alias[old] = bucket["name"]

    by_name = {m.name: m for m in bucket_matchers}
    lots_by_key = {str(l.get("lot_number")): l for l in lots}

    pairs = 0
    shortlisted = 0
    per_bucket: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    unmatched_lots = 0
    # Lot-level: did the lot reach the model AT ALL, under any heading? A mouse
    # shortlisted as "Keyboards & PC peripherals" can still be assigned
    # "Electronics" by the model, so pair recall understates what is reachable.
    flagged_lots = 0
    reached_lots = 0

    for row in prev:
        key = str(row.get("lot_number"))
        lot = lots_by_key.get(key)
        if lot is None:
            unmatched_lots += 1
            continue
        text = haystack(lot)
        segments = crumb_segments(lot.get("category"))
        buckets_here = row.get("bats_buckets") or []
        if buckets_here:
            flagged_lots += 1
            if any(m.match(text, segments) is not None for m in bucket_matchers):
                reached_lots += 1
        for raw in buckets_here:
            name = alias.get(raw, raw)
            matcher = by_name.get(name)
            pairs += 1
            per_bucket[name][1] += 1
            if matcher is not None and matcher.match(text, segments) is not None:
                shortlisted += 1
                per_bucket[name][0] += 1

    if not pairs:
        print("No accepted (lot, bucket) pairs found in the previous file.")
        return 1

    print(f"Backtest against {prev_path}")
    if unmatched_lots:
        print(f"  {unmatched_lots} rows had a lot_number not in this slim file (different week)")
    print(f"\n  {'bucket':45s} {'recall':>8s}  hit/total")
    for name in sorted(per_bucket, key=lambda n: (per_bucket[n][0] / max(per_bucket[n][1], 1), n)):
        hit, total = per_bucket[name]
        flag = "  <-- " if total >= 10 and hit / total < 0.90 else ""
        print(f"  {name:45s} {100*hit/total:7.1f}%  {hit}/{total}{flag}")

    pct = 100 * shortlisted / pairs
    lot_pct = 100 * reached_lots / flagged_lots if flagged_lots else 0.0
    print(f"\n  PAIR recall (right bucket): {pct:.1f}%  ({shortlisted}/{pairs})")
    print(f"  LOT  recall (reached model): {lot_pct:.1f}%  ({reached_lots}/{flagged_lots})")
    if lot_pct < 97:
        print("\n  Lot recall below the 97% target — previously-flagged lots would not "
              "reach the model at all. Tighten seeds on the flagged buckets above.")
        return 1
    return 0


def run_audit(
    lots: list[dict],
    bucket_matchers: list[Matcher],
    pseudo_matchers: list[Matcher],
    flags_path: Path,
) -> int:
    """Compare what the model accepted against what it was shown."""
    flags = load_items(flags_path, "flags file")
    cand_by_lot, _, _ = shortlist(lots, bucket_matchers, pseudo_matchers)
    lots_by_key = {str(l.get("lot_number")): l for l in lots}

    accepted: dict[str, int] = Counter()
    outside: dict[str, int] = Counter()
    shown: dict[str, int] = Counter()
    for name, cands in ((n, c) for c in cand_by_lot.values() for n in c):
        shown[name] += 1

    picks_no_bucket = []
    for row in flags:
        key = str(row.get("lot_number"))
        cands = set(cand_by_lot.get(key, []))
        for name in row.get("bats_buckets") or []:
            accepted[name] += 1
            if name not in cands:
                outside[name] += 1
        if row.get("personal_match") is True and not (row.get("bats_buckets") or []):
            picks_no_bucket.append((key, row.get("personal_tags") or []))

    print(f"{'bucket':45s} {'shown':>7s} {'kept':>7s} {'rate':>7s}  {'outside':>7s}")
    for name in sorted(set(shown) | set(accepted)):
        s, a, o = shown.get(name, 0), accepted.get(name, 0), outside.get(name, 0)
        note = ""
        if s >= 20 and a == 0:
            note = "  <-- refused the whole bucket"
        elif s and a / s > 0.95:
            note = "  <-- shortlist is doing the judging; seeds too narrow"
        rate = f"{100*a/s:6.1f}%" if s else "     - "
        print(f"{name:45s} {s:7d} {a:7d} {rate}  {o:7d}{note}")

    if picks_no_bucket:
        print(f"\n{len(picks_no_bucket)} personal picks carry no bucket. Because the profile "
              f"now dictates the taxonomy, each of these is a seed gap. By tag:")
        for tag, n in Counter(t for _, tags in picks_no_bucket for t in tags).most_common(15):
            print(f"  {n:5d}  {tag}")

    # Terms common in accepted titles and rare in rejected ones are the
    # seeds this run was missing. Ranked by lift, existing seeds removed.
    known = {s for m in bucket_matchers for s in m.seeds}
    kept_lots = {str(r["lot_number"]) for r in flags if r.get("bats_buckets")}
    kept_terms, rest_terms = Counter(), Counter()
    for key, lot in lots_by_key.items():
        target = kept_terms if key in kept_lots else rest_terms
        words = re.findall(r"[a-z0-9]+", str(lot.get("title", "")).lower())
        target.update(set(words))
        target.update({f"{a} {b}" for a, b in zip(words, words[1:])})
    suggestions = []
    for term, n in kept_terms.items():
        if n < 8 or term in known or len(term) < 4:
            continue
        lift = n / (n + rest_terms.get(term, 0))
        if lift > 0.75:
            suggestions.append((lift, n, term))
    suggestions.sort(reverse=True)
    if suggestions:
        print("\nCandidate new seeds (frequent in accepted titles, rare elsewhere):")
        for lift, n, term in suggestions[:25]:
            print(f"  {n:5d}  {lift:.2f}  {term}")
    return 0


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 tools/prefilter.py")
    parser.add_argument("auction_id")
    parser.add_argument("--buckets", default="buckets.yaml")
    parser.add_argument("--profile", default="profile.yaml")
    parser.add_argument("--backtest", metavar="PATH",
                        help="measure seed recall against a previous categorized file")
    parser.add_argument("--audit", metavar="PATH",
                        help="compare a returned flags file against what was shortlisted")
    parser.add_argument("--max-bucket-share", type=float, default=DEFAULT_MAX_BUCKET_SHARE)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--sweep", type=int, default=DEFAULT_SWEEP)
    args = parser.parse_args(argv)

    aid = args.auction_id
    lots = load_items(Path(f"data/categorized/auction_{aid}_for_agent.json"), "slimmed file")
    buckets = load_yaml(Path(args.buckets), "buckets.yaml").get("buckets") or []
    profile = load_yaml(Path(args.profile), "profile.yaml")
    interests = profile.get("interests") or []

    bucket_matchers, pseudo_matchers = build_matchers(buckets, interests)

    lint_problems = lint_profile(buckets, interests)
    if lint_problems:
        print("Profile/bucket lint:", file=sys.stderr)
        for p in lint_problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    for warning in lint_examples(buckets):
        print(f"  WARNING: {warning}", file=sys.stderr)

    if args.backtest:
        return run_backtest(lots, bucket_matchers, buckets, Path(args.backtest))
    if args.audit:
        return run_audit(lots, bucket_matchers, pseudo_matchers, Path(args.audit))

    unconfigured = [m.name for m in bucket_matchers if not m.configured]
    cand_by_lot, profile_by_lot, seed_hits = shortlist(lots, bucket_matchers, pseudo_matchers)

    bucket_sizes = Counter()
    for names in cand_by_lot.values():
        bucket_sizes.update(names)

    rows = [
        candidate_row(lot, cand_by_lot.get(str(lot.get("lot_number")), []),
                      profile_by_lot.get(str(lot.get("lot_number")), []))
        for lot in lots
        if str(lot.get("lot_number")) in cand_by_lot
        or str(lot.get("lot_number")) in profile_by_lot
    ]
    rows, boundaries = order_candidates(rows, bucket_sizes)

    total = len(lots)
    print(f"{total} lots -> {len(rows)} candidates ({100*len(rows)/total:.1f}%)\n")
    print(f"  {'bucket':45s} {'lots':>7s} {'share':>7s}")
    for name in sorted(bucket_sizes, key=lambda n: -bucket_sizes[n]):
        n = bucket_sizes[name]
        print(f"  {name:45s} {n:7d} {100*n/total:6.1f}%")

    # --- guards ---------------------------------------------------------
    failures = []
    for name, n in bucket_sizes.items():
        if n / total > args.max_bucket_share:
            top = ", ".join(f"{s!r}({c})" for s, c in seed_hits[name].most_common(3))
            failures.append(
                f"{name}: {n} lots ({100*n/total:.1f}%) exceeds "
                f"--max-bucket-share {100*args.max_bucket_share:.0f}%. "
                f"Most productive seeds: {top}"
            )
    if len(rows) > args.max_rows:
        failures.append(
            f"{len(rows)} candidate rows exceeds --max-rows {args.max_rows}. "
            f"Tighten the largest buckets in the table above."
        )

    zero = sorted(set(m.name for m in bucket_matchers if m.configured) - set(bucket_sizes))
    if zero:
        print(f"\n  WARNING: {len(zero)} configured buckets shortlisted nothing "
              f"(a seed typo looks exactly like this): {zero}", file=sys.stderr)
    if unconfigured:
        print(f"\n  WARNING: {len(unconfigured)} buckets have no seeds or categories "
              f"and can never be shortlisted: {unconfigured}", file=sys.stderr)

    if failures:
        print()
        for f in failures:
            print(f"Error: {f}", file=sys.stderr)
        return 1

    # --- outputs --------------------------------------------------------
    out_dir = Path("data/categorized")
    sha = lot_set_sha(lots)

    base = [dict(BASE_ROW, lot_number=lot.get("lot_number")) for lot in lots]
    assert len(base) == total, "base file must carry exactly one row per lot"
    (out_dir / f"auction_{aid}_base.json").write_text(
        json.dumps({"lot_set_sha": sha, "source": f"auction_{aid}_for_agent.json",
                    "items": base}), encoding="utf-8")

    (out_dir / f"auction_{aid}_candidates.json").write_text(
        json.dumps(rows), encoding="utf-8")

    non_cand = [l for l in lots if str(l.get("lot_number")) not in cand_by_lot
                and str(l.get("lot_number")) not in profile_by_lot]
    sample = random.Random(SWEEP_SEED).sample(non_cand, min(args.sweep, len(non_cand)))
    (out_dir / f"auction_{aid}_sweep.json").write_text(
        json.dumps([candidate_row(l, [], []) for l in sample]), encoding="utf-8")

    (out_dir / f"auction_{aid}_prefilter.json").write_text(
        json.dumps({
            "lot_set_sha": sha,
            "total_lots": total,
            "candidates": len(rows),
            "bucket_sizes": dict(bucket_sizes),
            "zero_candidate_buckets": zero,
            "unconfigured_buckets": unconfigured,
            "boundaries": [{"bucket": b, "start": s, "count": c} for b, s, c in boundaries],
        }, indent=2), encoding="utf-8")

    print(f"\n  wrote {len(rows)} candidates, {total} base rows, "
          f"{len(sample)} sweep rows (lot_set_sha {sha})")
    print("\n  Paste boundaries — split chunks here so no bucket's run is cut in half:")
    for name, start, count in boundaries:
        print(f"    row {start:6d}  {name}  ({count})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
