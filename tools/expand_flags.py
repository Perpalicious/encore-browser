"""
Reconcile the chunked flagging responses and fan them out to every lot.

    python3 tools/expand_flags.py <ID>

Reads  data/categorized/auction_<ID>_chunk_NN.json        (from chunk_flagging.py)
       data/categorized/auction_<ID>_chunk_NN_flags.json  (from the ChatGPT pass)
       data/categorized/auction_<ID>_flag_groups.json     (from chunk_flagging.py)
Writes data/categorized/auction_<ID>_flags.json           (a row for EVERY lot)

The pass returns matches only. Roughly three lots in four are a "no", and a
full four-key row for each of those is ~95 bytes of the word `false` — around
60% of the response spent restating the default. Every product not named in a
response is therefore a judged non-match, and gets the all-false row here.

That trade costs the one property worth protecting: with negatives echoed you
can tell a judged "no" from a row the model silently skipped. Two things buy it
back, and neither depends on the model being honest about how far it got:

  - Chunks are real files. A response can only name lots that were in its own
    chunk, and anything outside it is a hard error rather than a row that
    quietly merges.
  - Every response must END with {"chunk_complete": "<last lot_number>"}.
    Truncation removes the tail, so a missing or wrong sentinel IS the
    truncation signal. It costs about forty bytes.

Fails loudly and writes nothing on any gap. `merge_categorized` replaces whole
rows and `build/` is lenient by design, so a short file here would otherwise
produce a clean, successful build quietly missing most of its flags.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# What a non-match looks like. Four keys, because merge_categorized replaces
# whole rows — a shorter row would drop bats_buckets/personal_match and turn
# personal_match into null in the bundle.
BASE_ROW = {"is_bats_list": False, "bats_buckets": [], "personal_match": False}

REQUIRED_KEYS = {"lot_number", "is_bats_list", "bats_buckets", "personal_match"}

# Each of these silently changes how build/ reads the file, or is a field the
# pass invented instead of the one asked for. See PROMPTS.md "Why this matters".
FORBIDDEN_KEYS = {
    "bats_category", "bats_subcategory", "category", "subcategory",
    "reasoning", "confidence",
}

SENTINEL_KEY = "chunk_complete"

# Carried from the representative onto every lot in its group. Everything the
# pass may return; anything else is rejected before we get here.
CARRY_FIELDS = [
    "is_bats_list", "bats_buckets", "bats_subtype", "personal_match",
    "personal_tags", "match_strength", "match_types", "personal_reasoning",
]


def load_json(path: Path, label: str):
    if not path.exists():
        sys.exit(f"Error: {label} not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(
            f"Error: {label} is not valid JSON ({exc}).\n"
            f"  {path}\n"
            f"  A response cut off mid-array lands here. Re-run that chunk; do "
            f"not hand-repair the file."
        )


def as_items(data, path: Path, label: str) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    sys.exit(f"Error: {label} must be a JSON array: {path}")


def check_chunk(n: int, chunk: list[dict], returned: list[dict],
                path: Path) -> tuple[dict[str, dict], list[str]]:
    """Validate one response against the chunk it was given."""
    problems: list[str] = []
    expected = {str(r["lot_number"]) for r in chunk}
    last_lot = str(chunk[-1]["lot_number"])

    if not returned:
        return {}, [f"chunk {n:02d}: response is empty"]

    sentinel_at = [i for i, r in enumerate(returned)
                   if isinstance(r, dict) and SENTINEL_KEY in r]
    if not sentinel_at:
        problems.append(
            f"chunk {n:02d}: no {{'{SENTINEL_KEY}': '{last_lot}'}} at the end. "
            f"The response was truncated, or the prompt's final rule was dropped."
        )
    else:
        if sentinel_at[-1] != len(returned) - 1:
            problems.append(
                f"chunk {n:02d}: {SENTINEL_KEY} is not the last element "
                f"(at index {sentinel_at[-1]} of {len(returned)})."
            )
        got = str(returned[sentinel_at[-1]].get(SENTINEL_KEY))
        if got != last_lot:
            problems.append(
                f"chunk {n:02d}: {SENTINEL_KEY} says {got!r} but the chunk ends "
                f"at {last_lot!r}. The pass stopped early."
            )

    matches: dict[str, dict] = {}
    unknown: list[str] = []
    for i, row in enumerate(returned):
        if not isinstance(row, dict):
            problems.append(f"chunk {n:02d}: element {i} is not an object")
            continue
        if SENTINEL_KEY in row:
            continue
        bad = FORBIDDEN_KEYS & row.keys()
        if bad:
            problems.append(
                f"chunk {n:02d}: row {i} carries forbidden key(s) "
                f"{sorted(bad)}. build/transform.py changes shape on these."
            )
            continue
        missing = REQUIRED_KEYS - row.keys()
        if missing:
            problems.append(
                f"chunk {n:02d}: row {i} is missing {sorted(missing)}")
            continue
        lot = str(row["lot_number"])
        if lot not in expected:
            unknown.append(lot)
            continue
        if lot in matches:
            problems.append(f"chunk {n:02d}: lot {lot} returned twice")
            continue
        if bool(row.get("is_bats_list")) != bool(row.get("bats_buckets")):
            problems.append(
                f"chunk {n:02d}: lot {lot} breaks `is_bats_list == "
                f"(bats_buckets is non-empty)`")
            continue
        matches[lot] = row

    if unknown:
        problems.append(
            f"chunk {n:02d}: {len(unknown)} returned lot_numbers were not in "
            f"this chunk — a hallucinated row, or the wrong file saved. "
            f"First few: {unknown[:5]}"
        )
    return matches, problems


def main(auction_id: str) -> None:
    out_dir = Path("data/categorized")
    chunk_paths = sorted(out_dir.glob(f"auction_{auction_id}_chunk_[0-9][0-9].json"))
    if not chunk_paths:
        sys.exit(
            f"Error: no chunk files for auction {auction_id}. "
            f"Run tools/chunk_flagging.py {auction_id} first."
        )

    groups: dict[str, list[str]] = load_json(
        out_dir / f"auction_{auction_id}_flag_groups.json", "group map")

    all_matches: dict[str, dict] = {}
    problems: list[str] = []
    judged = 0

    for path in chunk_paths:
        n = int(re.search(r"_chunk_(\d+)\.json$", path.name).group(1))
        chunk = as_items(load_json(path, f"chunk {n:02d}"), path, f"chunk {n:02d}")
        flags_path = out_dir / f"auction_{auction_id}_chunk_{n:02d}_flags.json"
        if not flags_path.exists():
            problems.append(
                f"chunk {n:02d}: no response saved. Expected {flags_path.name}")
            continue
        returned = as_items(
            load_json(flags_path, f"chunk {n:02d} response"), flags_path,
            f"chunk {n:02d} response")
        matches, chunk_problems = check_chunk(n, chunk, returned, flags_path)
        problems.extend(chunk_problems)
        dupes = matches.keys() & all_matches.keys()
        if dupes:
            problems.append(
                f"chunk {n:02d}: {len(dupes)} lots already judged by an earlier "
                f"chunk: {sorted(dupes)[:5]}")
        all_matches.update(matches)
        judged += len(chunk)
        print(f"  chunk {n:02d}: {len(chunk):,} products -> "
              f"{len(matches):,} matched, {len(chunk) - len(matches):,} no-match")

    if problems:
        sys.exit("\nError: the flagging responses did not reconcile.\n  "
                 + "\n  ".join(problems)
                 + "\n\nNothing was written. Re-run the chunks named above.")

    expanded: list[dict] = []
    for rep_lot, members in groups.items():
        match = all_matches.get(rep_lot)
        for lot_number in members:
            row = {"lot_number": lot_number}
            if match is None:
                row.update(BASE_ROW)
            else:
                for field in CARRY_FIELDS:
                    if match.get(field) is not None:
                        row[field] = match[field]
                for field, default in BASE_ROW.items():
                    row.setdefault(field, default)
            expanded.append(row)

    total_lots = sum(len(v) for v in groups.values())
    if len(expanded) != total_lots:
        sys.exit(f"Error: expanded {len(expanded)} rows for {total_lots} lots")
    if judged != len(groups):
        sys.exit(
            f"Error: chunks covered {judged:,} products but the group map has "
            f"{len(groups):,}. A chunk file is missing or was regenerated after "
            f"the run — re-run tools/chunk_flagging.py and redo the pass."
        )

    flagged = sum(1 for r in expanded if r.get("is_bats_list"))
    out = Path(f"data/categorized/auction_{auction_id}_flags.json")
    out.write_text(json.dumps(expanded), encoding="utf-8")
    print()
    print(f"{len(all_matches):,} matched products -> {len(expanded):,} lots "
          f"({flagged:,} flagged, {100 * flagged / len(expanded):.1f}%)")
    print(f"  wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
