#!/usr/bin/env python3
"""
Mid-week delta: flag only the lots that arrived since the week's full run.

    python3 tools/delta.py <ID> start
    python3 tools/delta.py <ID> merge

An auction keeps growing after the weekly passes have run (Tue ~12k lots, Thu
+6k, Fri +…). The build is strict — a raw lot with no categorized row is
dropped — so new lots reach the viewer only after they have been judged. This
tool turns that into a repeatable loop that fits every existing guard instead
of fighting them:

`start`
    Re-scrape first (both auctions on a two-auction week, then re-run the
    prefix + combine step exactly as in CLAUDE.md step 2). Then `start` finds
    the lots in `data/raw/auction_<ID>.json` that are neither in
    `auction_<ID>_categorized.json` nor in an earlier, still-unmerged delta,
    and writes them to `data/raw/auction_<ID>_dN.json`. It prints the exact
    commands to run next. Every normal tool (`slim.py`, `chunk_flagging.py`,
    `expand_flags.py`, …) takes `<ID>_dN` as its auction ID; their file names
    are literal `auction_<ID>_dN_*` and never collide with the parent week's.

`merge`
    Once `auction_<ID>_dN_flags.json` exists for every delta: re-run `slim.py`
    and `prefilter.py` on the *full* raw so `_for_agent.json`, `_base.json`
    and `_prefilter.json` describe the current lot set (and carry its fresh
    `lot_set_sha`), then fold the week's categorized rows and every delta's
    flags onto that base. Resale valuations fold the same way. Then CLAUDE.md
    steps 5 (verify) to 9 run unchanged.

    Lots pulled from the auction between scrapes are routine
    (`python -m build --drop-orphans` exists for them). Each layer is
    restricted to the current lot set *before* folding, and the drops are
    reported; without that `merge_categorized` would count them as additions
    and `verify_passes.py` would fail on "lot_numbers not in this week's
    auction". After the restriction `n_added` must be 0 on every layer — a
    non-zero count means a hallucinated or mis-filed row and is fatal.

    Re-running `merge` is safe: the same layers fold to the same result.

The never-re-run rule for `tools/chunk_flagging.py <ID>` still applies to the
parent ID; chunking under `<ID>_dN` is what this loop expects.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diff_categorized.__main__ import _load_items as load_raw, diff  # noqa: E402
from merge_categorized.__main__ import _atomic_write_json, merge as merge_rows  # noqa: E402

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/categorized")
_TZ = ZoneInfo("America/New_York")
_DELTA_RE = re.compile(r"_d(\d+)\.json$")


class DeltaError(Exception):
    pass


# --- pure helpers ---------------------------------------------------------

def delta_paths(aid: str, raw_dir: Path = RAW_DIR) -> list[tuple[int, Path]]:
    """Existing delta raw files for this week, as (N, path), ascending."""
    found = []
    for path in raw_dir.glob(f"auction_{aid}_d*.json"):
        m = _DELTA_RE.search(path.name)
        if m and path.name == f"auction_{aid}_d{m.group(1)}.json":
            found.append((int(m.group(1)), path))
    return sorted(found)


def next_delta_n(aid: str, raw_dir: Path = RAW_DIR) -> int:
    existing = delta_paths(aid, raw_dir)
    return existing[-1][0] + 1 if existing else 1


def known_keys(*item_lists: list[dict]) -> set[str]:
    """Every id and lot_number across the given item lists, as strings —
    the same join rule `diff_categorized` applies."""
    keys: set[str] = set()
    for items in item_lists:
        for item in items:
            for field in ("id", "lot_number"):
                value = item.get(field)
                if value is not None and value != "":
                    keys.add(str(value))
    return keys


def restrict(items: list[dict], lot_set: set[str]) -> tuple[list[dict], list[str]]:
    """Keep rows whose lot_number is in `lot_set`; return (kept, dropped lots)."""
    kept, dropped = [], []
    for item in items:
        ln = str(item.get("lot_number"))
        (kept if ln in lot_set else dropped).append(item)
    return kept, [str(d.get("lot_number")) for d in dropped]


def fold(base_items: list[dict], layers: list[tuple[str, list[dict]]],
         lot_set: set[str]) -> tuple[list[dict], list[str]]:
    """Fold each layer onto the base in order. Every layer is restricted to
    `lot_set` first; after that a lot the base does not know is fatal."""
    items = list(base_items)
    report: list[str] = []
    for name, rows in layers:
        kept, dropped = restrict(rows, lot_set)
        items, n_added, n_updated = merge_rows(items, kept)
        if n_added:
            raise DeltaError(
                f"{name}: {n_added} row(s) are in the current lot set but not "
                f"in the fresh _base.json — the base and the raw disagree; "
                f"re-run tools/slim.py and tools/prefilter.py and try again")
        note = f"dropped {len(dropped)} (no longer in the auction)" if dropped else "dropped 0"
        report.append(f"{name:12s} applied {n_updated:>6,} rows, {note}")
    return items, report


def _dates(items: list[dict]) -> Counter:
    out: Counter = Counter()
    for item in items:
        try:
            dt = datetime.fromisoformat(str(item["first_seen"]).replace("Z", "+00:00"))
            out[dt.astimezone(_TZ).strftime("%a %b %d %H:%M")] += 1
        except (KeyError, ValueError):
            out["(no first_seen)"] += 1
    return out


# --- commands ---------------------------------------------------------------

def start(aid: str) -> None:
    raw_path = RAW_DIR / f"auction_{aid}.json"
    cat_path = OUT_DIR / f"auction_{aid}_categorized.json"
    if not raw_path.exists():
        sys.exit(f"Error: raw file not found: {raw_path}. Re-scrape first.")
    if not cat_path.exists():
        sys.exit(f"Error: {cat_path} not found. A delta only makes sense after "
                 f"the week's full run (CLAUDE.md steps 1-9).")

    raw_items, raw_env = load_raw(raw_path, "raw")
    cat_items, _ = load_raw(cat_path, "categorized")
    prior = delta_paths(aid)
    prior_items = [load_raw(p, f"d{n}")[0] for n, p in prior]

    # diff() keys on the categorized side's id/lot_number; feeding it the
    # earlier deltas' raw items makes those count as known too.
    known = [dict(lot_number=k) for k in known_keys(cat_items, *prior_items)]
    new_items = diff(raw_items, known)
    if not new_items:
        sys.exit(f"Nothing to do: every lot in {raw_path} is already categorized"
                 + (f" or in d{prior[-1][0]}" if prior else "") + ".")

    missing = [str(i.get("lot_number")) for i in new_items if not i.get("first_seen")]
    if missing:
        sys.exit(f"Error: {len(missing)} new lot(s) carry no first_seen (e.g. "
                 f"{missing[:3]}). The raw file was not written by the current "
                 f"scraper — re-scrape before starting a delta.")

    n = next_delta_n(aid)
    did = f"{aid}_d{n}"
    out_path = RAW_DIR / f"auction_{did}.json"
    envelope = {k: v for k, v in raw_env.items() if k != "item_count"}
    envelope.update({"parent": aid, "delta": n, "item_count": len(new_items),
                     "items": new_items})
    _atomic_write_json(out_path, envelope)

    print(f"{len(new_items)} new lots of {len(raw_items)} in the raw "
          f"({len(cat_items)} categorized"
          + (f", {sum(len(p) for p in prior_items)} in earlier deltas" if prior else "")
          + f") -> {out_path}")
    for when, count in sorted(_dates(new_items).items()):
        print(f"  first seen {when}: {count:,}")

    print(f"""
Next — the normal pass, under the delta ID `{did}`:

  python3 tools/slim.py {did}
  python3 tools/slim_resale.py {did}        # skip on a flagging-only week
  python3 tools/chunk_flagging.py {did}

then one ChatGPT chat per printed prompt (and the resale chat), saving each
reply under the name its prompt states, then:

  python3 tools/expand_flags.py {did}
  python3 tools/recall_check.py {did} plan   # then the recall chat, then `apply`
  python3 tools/expand_resale.py {did}       # resale weeks only
  python3 tools/delta.py {aid} merge

Do NOT run tools/chunk_flagging.py {aid} — the parent week's chunks stay as
they were judged.""")


def merge(aid: str, *, run_tools: bool = True) -> None:
    deltas = delta_paths(aid)
    if not deltas:
        sys.exit(f"Error: no data/raw/auction_{aid}_dN.json — run `start` first.")

    flag_paths = {n: OUT_DIR / f"auction_{aid}_d{n}_flags.json" for n, _ in deltas}
    missing = [p for p in flag_paths.values() if not p.exists()]
    if missing:
        sys.exit("Error: every delta needs its expanded flags before merging; "
                 "missing:\n  " + "\n  ".join(str(p) for p in missing)
                 + "\nRun tools/expand_flags.py <ID>_dN for each.")

    cat_path = OUT_DIR / f"auction_{aid}_categorized.json"
    if not cat_path.exists():
        sys.exit(f"Error: {cat_path} not found.")
    # Load the week's rows before anything is regenerated.
    cat_items, _ = load_raw(cat_path, "categorized")

    if run_tools:
        # Fresh _for_agent / _base / _prefilter for the FULL current raw. Both
        # tools exit non-zero on their own tripwires; a stale base is worse
        # than stopping here.
        for tool in ("tools/slim.py", "tools/prefilter.py"):
            print(f"\n== {tool} {aid} ==")
            subprocess.run([sys.executable, tool, aid], check=True)
        print()

    base_path = OUT_DIR / f"auction_{aid}_base.json"
    base_items, base_env = load_raw(base_path, "base")
    lot_set = {str(i.get("lot_number")) for i in base_items}

    layers: list[tuple[str, list[dict]]] = [("categorized", cat_items)]
    resale_layers: list[tuple[str, list[dict]]] = []
    for n, _ in deltas:
        did = f"{aid}_d{n}"
        flags, _ = load_raw(flag_paths[n], f"d{n} flags")
        slim_path = OUT_DIR / f"auction_{did}_for_agent.json"
        if slim_path.exists():
            judged = {str(i.get("lot_number")) for i in load_raw(slim_path, "slim")[0]}
            foreign = sorted({str(f.get("lot_number")) for f in flags} - judged)
            if foreign:
                sys.exit(f"Error: {flag_paths[n]} has {len(foreign)} lot_number(s) "
                         f"that were never in {slim_path} (e.g. {foreign[:3]}).")
        layers.append((f"d{n}", flags))
        resale_path = OUT_DIR / f"auction_{did}_resale.json"
        if resale_path.exists():
            resale_layers.append((f"d{n}", load_raw(resale_path, f"d{n} resale")[0]))
        else:
            print(f"note: no {resale_path.name} — delta d{n} carries no valuations")

    try:
        merged, report = fold(base_items, layers, lot_set)
    except DeltaError as exc:
        sys.exit(f"Error: {exc}")
    envelope = dict(base_env)
    envelope["deltas"] = [n for n, _ in deltas]
    envelope["item_count"] = len(merged)
    envelope["items"] = merged
    _atomic_write_json(cat_path, envelope)
    print(f"categorized -> {cat_path} ({len(merged):,} rows, lot_set_sha "
          f"{envelope.get('lot_set_sha')})")
    for line in report:
        print(f"  {line}")

    resale_path = OUT_DIR / f"auction_{aid}_resale.json"
    if resale_path.exists():
        resale_items, _ = load_raw(resale_path, "resale")
        kept, dropped = restrict(resale_items, lot_set)
        print(f"resale       kept {len(kept):,} rows, dropped {len(dropped)} "
              f"(no longer in the auction)")
        for name, rows in resale_layers:
            rows, r_dropped = restrict(rows, lot_set)
            kept, n_added, n_updated = merge_rows(kept, rows)
            print(f"  {name:12s} added {n_added:>6,} rows, updated {n_updated}, "
                  f"dropped {len(r_dropped)}")
        _atomic_write_json(resale_path, kept)
        print(f"resale -> {resale_path} ({len(kept):,} rows)")
    elif resale_layers:
        print("note: the week has no _resale.json, so delta valuations were not merged")

    print(f"""
Next — CLAUDE.md steps 5 to 9 for `{aid}`:

  python3 tools/verify_passes.py {aid}{'' if resale_path.exists() else ' --no-resale'}
  python -m build ...                 # step 6, unchanged flags
  (bundle verification snippet)       # step 7 — expect one more scrape listed
  cd viewer && npm run build && npx gh-pages -d dist -b gh-pages && cd ..
  git add -A && git commit -m "Update bundle: auction {aid} (delta{'s' if len(deltas) > 1 else ''} {', '.join(f'd{n}' for n, _ in deltas)})" && git push""")


def main(argv: list[str]) -> None:
    if len(argv) != 2 or argv[1] not in ("start", "merge"):
        sys.exit(__doc__)
    aid, command = argv
    (start if command == "start" else merge)(aid)


if __name__ == "__main__":
    main(sys.argv[1:])
