"""
Find lots the flagging pass probably missed, and re-judge only those.

    python3 tools/recall_check.py <ID> plan     # finds suspects, builds the repair chat
    python3 tools/recall_check.py <ID> apply    # folds its response into _flags.json

plan reads  data/categorized/auction_<ID>_for_agent.json     (this week's slim)
            data/categorized/auction_<ID>_flag_groups.json   (from chunk_flagging.py)
            data/categorized/auction_<ID>_flags.json         (from expand_flags.py)
            buckets.yaml
     writes data/categorized/auction_<ID>_recall.json         (the chat's input)
            data/categorized/auction_<ID>_recall_prompt.md    (its prompt)

apply reads the same plus auction_<ID>_recall_flags.json (the response)
      writes auction_<ID>_flags.json with the confirmed lots flagged, keeping
             the original as auction_<ID>_flags_before_recall.json. Then run
             merge_categorized and verify_passes exactly as before.

Runs between `expand_flags.py` and `merge_categorized` — it needs the whole
auction's answers, and it must finish before those answers are merged.

Why
---
The pass reads type words well and product names badly. On 2026-09-13 it
flagged every Logitech lot whose title said KEYBOARD or MOUSE and none of the
seven that said only "MX KEYS FOR MAC" or "MX ANYWHERE 3S MAC COMPACT
WIRELESS" — one of them sitting between two flagged MX Keys rows. Same run,
larger: "PHYLOSAL A3 LED LIGHT PAD FOR DIAMOND PAINTING" went to Kids' craft
44 times, and the 64 lots of the same pad titled "ULTRA-THIN BOX" or
"RECHARGEABLE LIGHT BOARD" went nowhere. Every one of those rows reached the
model intact; it just did not recognise them without the type word.

Those misses are detectable from the run's own output. Two shapes:

  sibling  the product shares its leading title words with a product the
           pass DID flag, and got nothing. The flagged sibling is evidence.
  seed     the product matches one of a bucket's own seed words, sits in a
           HiBid category that bucket dominates this week, is not on the
           bucket's exclude list, and got nothing.

Neither is proof — "10-IN-1 STEAM MOP" and "10-IN-1 URINE TEST STRIPS" share
three words, and a toy Dyson matches "vacuum" — so the suspects go to one
small chat that is asked a much narrower question than the pass was: here is
the lot, here is why it is suspect, confirm or refuse. Pairwise judgment
against a named sibling is a task the model is good at; spotting one
unrecognised row in 2,750 is the task it is bad at. A run's worth of suspects
is a few hundred products, a fraction of one chunk.

What it cannot see: a product with no flagged sibling and no seed match. That
residual is real, and only a person noticing shrinks it.

Only products with NO bucket are candidates. A product already on Bat's List
that might deserve a second bucket is a different, smaller problem, and
including those would make the chat rewrite rows the pass already got right.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

try:
    from tools import expand_flags, render_prompts
except ImportError:  # run directly as `python3 tools/<script>.py`
    import expand_flags
    import render_prompts

OUT_DIR = Path("data/categorized")

# A HiBid category is "dominated" by a bucket when the pass put at least this
# share of its lots there. Categories under MIN_CATEGORY_LOTS are too small to
# say anything either way.
DOMINANCE = 0.60
MIN_CATEGORY_LOTS = 15

# Seeds shorter than this ("tkl", "usb") match too freely to be evidence.
MIN_SEED_LEN = 4

# Leading title tokens that define a product family. Purely numeric tokens
# and single characters are skipped first, so "45 J'S.O.L.E COWBOY BOOTS" and
# "L AVIDLOVE WOMENS ..." key on the words that identify the product, not the
# size that Encore front-loads.
#
# Three words is the main key. Two words is used as well, but only when the
# second word is a line code ("PHYLOSAL A3", "LOGITECH MX") and only for a
# bucket that took at least DOMINANCE of the family's flagged lots — an MX
# board is legitimately both Keyboards and Electronics, but Keyboards is
# where the family lives. Brand pairs ("PHILIPS AVENT", "LA ROCHE", "CALVIN
# KLEIN") span product types and would put every unflagged lot of the brand
# up for review; measured 2026-09-14 they doubled the list.
SIBLING_WORDS = 3
SHORT_SIBLING_WORDS = 2


def _load(path: Path, label: str):
    if not path.exists():
        sys.exit(f"Error: {label} not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _items(data) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    return data


def _is_line_code(word: str) -> bool:
    return len(word) <= 2 or any(ch.isdigit() for ch in word)


def sibling_key(title: str, n: int = SIBLING_WORDS) -> str | None:
    """The leading `n` product words of a title, or None if they do not form
    a family key (too few words, or a short key that is not BRAND + code)."""
    tokens = re.sub(r"[^A-Z0-9 ]", " ", (title or "").upper()).split()
    words = [t for t in tokens if len(t) > 1 and not t.isdigit()]
    if len(words) < n:
        return None
    if n < SIBLING_WORDS:
        if not (words[0].isalpha() and _is_line_code(words[1])):
            return None
    elif sum(1 for w in words[:n] if w.isalpha()) < 2:
        return None
    return " ".join(words[:n])


def _seed_patterns(buckets: list[dict]) -> dict[str, tuple[re.Pattern | None, re.Pattern | None]]:
    """Per bucket: (seed regex, exclude regex). Either may be None."""
    out = {}
    for b in buckets:
        seeds = [s for s in (b.get("seeds") or []) if len(s) >= MIN_SEED_LEN]
        seed_re = re.compile(
            r"\b(" + "|".join(re.escape(s) for s in seeds) + r")", re.I) if seeds else None
        excl = b.get("exclude") or []
        excl_re = re.compile("|".join(re.escape(s) for s in excl), re.I) if excl else None
        out[b["name"]] = (seed_re, excl_re)
    return out


def find_suspects(slim: list[dict], groups: dict[str, list[str]],
                  flags: list[dict], buckets: list[dict]) -> list[dict]:
    """Unflagged products with evidence they belong in a bucket.

    Returns one row per product (group representative), each carrying the
    representative's slim fields, `qty`, and a `suspect` list of
    {bucket, because} pairs — the evidence the repair chat is shown.
    """
    by_lot = {str(r["lot_number"]): r for r in slim}
    flag_of = {str(r["lot_number"]): r for r in flags}
    patterns = _seed_patterns(buckets)

    def buckets_of(lot: str) -> list[str]:
        return list(flag_of.get(lot, {}).get("bats_buckets") or [])

    # Product-level view: representative -> members. Flags are identical
    # within a group, so the representative's row speaks for all of them.
    reps = [(rep, members) for rep, members in groups.items() if rep in by_lot]

    # Which HiBid categories the pass treats as one bucket's territory.
    cat_lots: dict[str, int] = Counter()
    cat_bucket: dict[str, Counter] = defaultdict(Counter)
    for rep, members in reps:
        cat = by_lot[rep].get("category") or ""
        cat_lots[cat] += len(members)
        for b in buckets_of(rep):
            cat_bucket[cat][b] += len(members)
    dominant: dict[str, str] = {}
    for cat, n in cat_lots.items():
        if n < MIN_CATEGORY_LOTS or not cat_bucket[cat]:
            continue
        b, k = cat_bucket[cat].most_common(1)[0]
        if k / n >= DOMINANCE:
            dominant[cat] = b

    # Which product families the pass flagged, and where.
    family: dict[str, dict[str, list[tuple[str, int]]]] = defaultdict(lambda: defaultdict(list))
    short_family: dict[str, dict[str, list[tuple[str, int]]]] = defaultdict(lambda: defaultdict(list))
    short_flagged: Counter = Counter()          # flagged lots per short family
    for rep, members in reps:
        title = by_lot[rep].get("title", "")
        flagged_into = buckets_of(rep)
        for table, n in ((family, SIBLING_WORDS), (short_family, SHORT_SIBLING_WORDS)):
            key = sibling_key(title, n)
            if key is None:
                continue
            if table is short_family and flagged_into:
                short_flagged[key] += len(members)
            for b in flagged_into:
                table[key][b].append((title, len(members)))
    # The short key only counts for the bucket(s) a family clearly lives in.
    for key, per_bucket in list(short_family.items()):
        short_family[key] = {
            b: flagged for b, flagged in per_bucket.items()
            if sum(q for _, q in flagged) / short_flagged[key] >= DOMINANCE
        }

    suspects = []
    for rep, members in reps:
        if buckets_of(rep):
            continue
        rec = by_lot[rep]
        title = rec.get("title", "")
        evidence: dict[str, str] = {}

        for table, n in ((family, SIBLING_WORDS), (short_family, SHORT_SIBLING_WORDS)):
            key = sibling_key(title, n)
            if key is None:
                continue
            for b, flagged in table.get(key, {}).items():
                _, excl_re = patterns.get(b, (None, None))
                if b in evidence or (excl_re and excl_re.search(title)):
                    continue
                # Show the most-copied flagged sibling; it is the clearest case.
                sib_title, sib_qty = max(flagged, key=lambda t: t[1])
                evidence[b] = (f"the pass flagged {sib_qty} lot(s) of "
                               f"\"{sib_title}\" here")

        cat = rec.get("category") or ""
        b = dominant.get(cat)
        if b and b not in evidence:
            seed_re, excl_re = patterns.get(b, (None, None))
            if seed_re and not (excl_re and excl_re.search(title)):
                m = seed_re.search(title)
                if m:
                    share = cat_bucket[cat][b] / cat_lots[cat]
                    evidence[b] = (f"title contains \"{m.group(0)}\" and the pass "
                                   f"sent {share:.0%} of this HiBid category here")

        if not evidence:
            continue
        row = {k: v for k, v in rec.items() if k != "description" or v}
        row["qty"] = len(members)
        row["suspect"] = [{"bucket": b, "because": why} for b, why in evidence.items()]
        suspects.append(row)

    suspects.sort(key=lambda r: (r["suspect"][0]["bucket"], r.get("title", "")))
    return suspects


def _table(suspects: list[dict]) -> None:
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in suspects:
        for s in r["suspect"]:
            per[s["bucket"]][0] += 1
            per[s["bucket"]][1] += r["qty"]
    print(f"\n  {'bucket':40} {'products':>8} {'lots':>6}")
    for b, (p, n) in sorted(per.items(), key=lambda x: -x[1][1]):
        print(f"  {b[:40]:40} {p:8d} {n:6d}")


def plan(auction_id: str) -> None:
    slim = _items(_load(OUT_DIR / f"auction_{auction_id}_for_agent.json", "slimmed file"))
    groups = _load(OUT_DIR / f"auction_{auction_id}_flag_groups.json", "group map")
    flags = _items(_load(OUT_DIR / f"auction_{auction_id}_flags.json",
                         "flags file (run tools/expand_flags.py first)"))
    buckets = yaml.safe_load(Path("buckets.yaml").read_text(encoding="utf-8"))["buckets"]

    suspects = find_suspects(slim, groups, flags, buckets)
    n_lots = sum(r["qty"] for r in suspects)
    total = sum(len(m) for m in groups.values())
    print(f"{len(suspects):,} unflagged products look like misses, covering "
          f"{n_lots:,} lots ({100 * n_lots / total:.1f}% of the auction)")
    if not suspects:
        print("  nothing to re-judge")
        return
    _table(suspects)

    src = OUT_DIR / f"auction_{auction_id}_recall.json"
    src.write_text(json.dumps(suspects), encoding="utf-8")
    prompt_path = OUT_DIR / f"auction_{auction_id}_recall_prompt.md"
    prompt_path.write_text(render_prompts.render("recall.md", {
        "CONTEXT_FILE": "context.yaml",
        "INPUT_FILE": src.name,
        "OUTPUT_FILE": f"auction_{auction_id}_recall_flags.json",
        "N": f"{len(suspects):,}",
        "LAST_LOT": str(suspects[-1]["lot_number"]),
        "N_BUCKETS": str(len(buckets)),
    }), encoding="utf-8")
    print(f"\n  wrote {src}")
    print()
    print("Recall repair (1 chat), attach context.yaml like the flagging chats:")
    print(f"  paste  {prompt_path}")
    print(f"  attach {OUT_DIR / 'context.yaml'}")
    print(f"  attach {src}")
    print(f"  save   {OUT_DIR / f'auction_{auction_id}_recall_flags.json'}")
    print(f"then: python3 tools/recall_check.py {auction_id} apply")


def apply(auction_id: str) -> None:
    src = OUT_DIR / f"auction_{auction_id}_recall.json"
    suspects = _items(_load(src, "recall input (run `plan` first)"))
    resp_path = OUT_DIR / f"auction_{auction_id}_recall_flags.json"
    returned = expand_flags.as_items(
        expand_flags.load_json(resp_path, "recall response"), resp_path, "recall response")
    groups = _load(OUT_DIR / f"auction_{auction_id}_flag_groups.json", "group map")
    flags_path = OUT_DIR / f"auction_{auction_id}_flags.json"
    flags = _items(_load(flags_path, "flags file"))

    matches, problems = expand_flags.check_chunk(0, suspects, returned, resp_path,
                                                 label="recall chat")
    if problems:
        sys.exit("\nError: the recall response did not reconcile.\n  "
                 + "\n  ".join(problems)
                 + "\n\nNothing was written. Re-run the recall chat.")

    by_lot = {str(r["lot_number"]): r for r in flags}
    already = [lot for lot in matches if by_lot.get(lot, {}).get("bats_buckets")]
    if already:
        sys.exit(f"\nError: {len(already)} confirmed lots already carry a bucket in "
                 f"{flags_path.name} — was `apply` run twice? Nothing written. "
                 f"First few: {already[:5]}")

    confirmed_lots = 0
    per_bucket: Counter = Counter()
    for rep, row in matches.items():
        for lot in groups.get(rep, [rep]):
            new = {"lot_number": lot}
            for field in expand_flags.CARRY_FIELDS:
                if row.get(field) is not None:
                    new[field] = row[field]
            for field, default in expand_flags.BASE_ROW.items():
                new.setdefault(field, default)
            by_lot[lot] = new
            confirmed_lots += 1
        for b in row.get("bats_buckets") or []:
            per_bucket[b] += len(groups.get(rep, [rep]))

    backup = flags_path.with_name(f"auction_{auction_id}_flags_before_recall.json")
    if not backup.exists():
        shutil.copy(flags_path, backup)
    flags_path.write_text(json.dumps([by_lot[str(r["lot_number"])] for r in flags]),
                          encoding="utf-8")

    refused = len(suspects) - len(matches)
    print(f"{len(matches):,} of {len(suspects):,} suspects confirmed "
          f"({refused:,} refused) -> {confirmed_lots:,} lots newly flagged")
    for b, n in per_bucket.most_common():
        print(f"  {b[:40]:40} +{n}")
    print(f"  original kept at {backup}")
    print(f"  rewrote {flags_path} — continue with merge_categorized as usual")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in ("plan", "apply"):
        sys.exit(__doc__)
    {"plan": plan, "apply": apply}[sys.argv[2]](sys.argv[1])
