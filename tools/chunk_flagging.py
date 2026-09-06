"""
Deduplicate the auction by product and cut it into upload-sized flagging chunks.

    python3 tools/chunk_flagging.py <ID> [--rows 2750]

Reads  data/categorized/auction_<ID>_for_agent.json
Writes data/categorized/auction_<ID>_chunk_NN.json     (one upload each)
       data/categorized/auction_<ID>_flag_groups.json  (fan-out map)
       data/categorized/context.yaml                   (buckets + profile, one upload)

Why dedup
---------
These auctions run the same product dozens of times — measured on 2026-08-30,
the Revlon One-Step dryer appeared in 129 separate lots, the Shark FlexBreeze
fan in 114, the Logitech MK270 in 99. Whether Bat wants a Revlon One-Step is
one judgment, not 129, and asking 129 times invites the model to answer
differently in different chunks.

This is NOT filtering. `tools/prefilter.py`'s shortlist decides some lots never
reach the model at all, and the bid history says what that costs: of 234 lots
actually bid on, 94 (40%) match no seed and are lexically invisible
(data/Watch/FINDINGS.md). Dedup makes no judgment call and loses no coverage —
every lot gets an answer via `tools/expand_flags.py`. On the week of
2026-08-30 it took 25,195 lots to 19,250 distinct products, 24% fewer.

Why chunk at all
----------------
A pass covering the whole auction cannot complete in one response. The last
real run (2026-08-16) returned 1.33 MB across 10,033 rows — roughly 347K output
tokens, many times any single-response ceiling. It completed only because
`PROMPTS.md` invites the model to stop at a row boundary and report where it
got to, which means the model chose every boundary and nothing verified them.

Chunk files move that boundary somewhere checkable. A chunk is a real file, so
the model cannot return a lot it was not given, and `tools/expand_flags.py`
reconciles what came back against a known exact input.

Grouping
--------
The key is every field that can change the answer: title, model, size,
condition, notes, the damage free text and the three condition flags. Matching
is exact — near-miss titles stay separate, which costs some redundancy but can
never merge two genuinely different products. Same rule as
`tools/slim_resale.py`, deliberately, so the two passes group identically.

Note that HiBid moved Model, Verified Size and the damage flags into a rendered
report image during the week of 2026-08-30, so those fields are now empty on
every lot and the key is title + condition in practice. Keeping them listed
costs nothing and makes the grouping self-healing if HiBid restores them.

Ordering
--------
Groups are sorted by category, then title, before cutting. Chunk boundaries
therefore fall inside a category rather than at its edge, so each chunk is
mostly one kind of thing. Each cut is then snapped to the nearest point where
the leading title words change, so a run of near-identical products is never
split across two chats — see `boundary_key`. Chunk sizes vary by a few rows as
a result. That is the only benefit the old four-way
category split (`passes.yaml`) actually bought — its `focus_buckets` hint never
narrowed anything, since `buckets.yaml` is attached in full to every pass
either way (docs/PASS_SOURCES.md section 1). Here every chunk gets the
identical prompt and the identical full taxonomy.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Every field that can change whether Bat wants this, or which bucket it is.
# Title is handled separately. Mirrors tools/slim_resale.py VALUE_FIELDS.
GROUP_FIELDS = [
    "model",
    "size",
    "condition",
    "notes",
    "damage",
    "missing_parts",
    "damaged",
    "missing_major_parts",
    "functional",
]

# Rows per chunk. Sized so one response stays well inside a single-response
# output ceiling: at ~169 bytes per flagged row (measured 2026-08-16) and a
# ~25% flag rate, 2,750 rows is roughly 30K output tokens.
DEFAULT_ROWS = 2750

# Leading title words that define a run of near-identical products. Two is
# enough to hold "SHARK FLEXSTYLE ..." together without gluing all of "SHARK"
# into one run: measured on 2026-08-30, one word gives runs up to 205 rows,
# two gives 75, three gives 26.
BOUNDARY_WORDS = 2

# How far a cut may travel from the target row count to reach a run boundary,
# as a share of the chunk size. 10% of 2,750 is 275 rows — comfortably more
# than the longest run above, so a boundary is always reachable and the
# fallback below never fires in practice.
BOUNDARY_DRIFT = 0.10

CONFIG_FILES = ("buckets.yaml", "profile.yaml")


def group_key(rec: dict) -> tuple:
    return (rec.get("title", "").strip().upper(),) + tuple(
        str(rec.get(f, "")).strip().upper() for f in GROUP_FIELDS
    )


def build_context(dst: Path) -> tuple[int, int]:
    """Concatenate buckets.yaml and profile.yaml into the single config upload.

    They always travel together — docs/PASS_SOURCES.md requires both on every
    flagging pass, in full — so shipping them as one file halves the uploads
    and removes the chance of attaching one and forgetting the other.
    """
    parts = []
    for name in CONFIG_FILES:
        path = Path(name)
        if not path.exists():
            sys.exit(f"Error: {name} not found. Run from the repo root.")
        parts.append(
            f"# ===== {name} "
            f"{'=' * max(0, 60 - len(name))}\n\n"
            f"{path.read_text(encoding='utf-8').rstrip()}\n"
        )
    text = "\n\n".join(parts)
    dst.write_text(text, encoding="utf-8")

    import yaml

    buckets = yaml.safe_load(Path("buckets.yaml").read_text(encoding="utf-8"))
    n_buckets = len(buckets.get("buckets", buckets))
    return n_buckets, len(text)


def boundary_key(rec: dict) -> tuple:
    """What a chunk boundary must not cut through.

    Products are sorted by category then title, so near-identical items sit
    next to each other — the FlexStyle stylers, then the FlexStyle filters.
    Cutting mid-run sends them to two different chats, which is the one place
    this design can produce inconsistent answers for near-identical products:
    dedup already guarantees that *identical* ones share a single judgment.
    """
    title = " ".join(str(rec.get("title") or "").upper().split())
    return (str(rec.get("category") or ""),
            " ".join(title.split(" ")[:BOUNDARY_WORDS]))


def split_rows(rows: list[dict], target: int,
               drift: int | None = None) -> tuple[list[list[dict]], int]:
    """Cut into chunks of ~target rows, snapping each cut to a run boundary.

    `drift` is how far a cut may travel to find one, defaulting to
    BOUNDARY_DRIFT of the target. Returns (chunks, forced) where `forced`
    counts cuts that had to land mid-run because no boundary was reachable.
    Chunk sizes therefore vary by a few rows either side of `target`.
    """
    if drift is None:
        drift = max(1, int(target * BOUNDARY_DRIFT))
    chunks: list[list[dict]] = []
    forced = 0
    start = 0
    while start < len(rows):
        end = start + target
        if end >= len(rows):
            chunks.append(rows[start:])
            break
        if boundary_key(rows[end - 1]) == boundary_key(rows[end]):
            snapped = None
            for delta in range(1, drift + 1):
                ahead = end + delta
                if (ahead < len(rows)
                        and boundary_key(rows[ahead - 1]) != boundary_key(rows[ahead])):
                    snapped = ahead
                    break
                behind = end - delta
                if (behind > start
                        and boundary_key(rows[behind - 1]) != boundary_key(rows[behind])):
                    snapped = behind
                    break
            if snapped is None:
                forced += 1
            else:
                end = snapped
        chunks.append(rows[start:end])
        start = end
    return chunks, forced


def main(auction_id: str, rows_per_chunk: int = DEFAULT_ROWS) -> None:
    src = Path(f"data/categorized/auction_{auction_id}_for_agent.json")
    if not src.exists():
        sys.exit(f"Error: slimmed file not found: {src}. Run tools/slim.py first.")
    if rows_per_chunk < 1:
        sys.exit("Error: --rows must be at least 1")

    slim = json.loads(src.read_text(encoding="utf-8"))
    if not slim:
        sys.exit(f"Error: {src} is empty")

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for rec in slim:
        groups[group_key(rec)].append(rec)

    representatives: list[dict] = []
    fan_out: dict[str, list[str]] = {}
    for members in groups.values():
        # Stable representative so re-running produces identical files.
        members = sorted(members, key=lambda r: str(r.get("lot_number")))
        rep = dict(members[0])
        # Real signal for a flipper, and it costs four characters: 129 copies
        # of one item is a saturated local market.
        rep["qty"] = len(members)
        representatives.append(rep)
        fan_out[str(rep["lot_number"])] = [str(m["lot_number"]) for m in members]

    covered = sum(len(v) for v in fan_out.values())
    if covered != len(slim):
        sys.exit(f"Error: fan-out covers {covered} lots but input had {len(slim)}")

    # Category then title, so a chunk boundary falls inside a category.
    representatives.sort(
        key=lambda r: (str(r.get("category") or ""), str(r.get("title") or ""),
                       str(r.get("lot_number"))))

    chunks, forced = split_rows(representatives, rows_per_chunk)

    out_dir = Path("data/categorized")
    for old in sorted(out_dir.glob(f"auction_{auction_id}_chunk_*.json")):
        old.unlink()

    written: list[tuple[Path, int, str]] = []
    for n, chunk in enumerate(chunks, start=1):
        path = out_dir / f"auction_{auction_id}_chunk_{n:02d}.json"
        path.write_text(json.dumps(chunk), encoding="utf-8")
        written.append((path, len(chunk), str(chunk[-1]["lot_number"])))

    groups_path = out_dir / f"auction_{auction_id}_flag_groups.json"
    groups_path.write_text(json.dumps(fan_out), encoding="utf-8")

    context_path = out_dir / "context.yaml"
    n_buckets, context_bytes = build_context(context_path)

    saved = len(slim) - len(representatives)
    print(f"{len(slim):,} lots -> {len(representatives):,} distinct products "
          f"({saved:,} repeats collapsed, {100 * saved / len(slim):.1f}% fewer)")
    print(f"  groups of 2+ : {sum(1 for v in fan_out.values() if len(v) > 1):,}")
    print(f"  largest group: {max(len(v) for v in fan_out.values()):,} lots")
    print(f"  wrote {groups_path}")
    print()
    if forced:
        print(f"  NOTE: {forced} cut(s) landed mid-run — no boundary within "
              f"{max(1, int(rows_per_chunk * BOUNDARY_DRIFT))} rows. Those "
              f"near-identical products are split across two chats.")
    print()
    print(f"UPLOAD {len(written) + 1} FILES ({n_buckets} buckets, "
          f"{context_bytes / 1024:.0f} KB of config):")
    print(f"  {context_path}   <- attach to EVERY chat")
    for path, n, last in written:
        print(f"  {path}   {n:,} rows, last lot_number {last}")
    print()
    print("Each chunk is judged with the same prompt (PROMPTS.md) and the same "
          "context.yaml.\nSave each response as "
          f"auction_{auction_id}_chunk_NN_flags.json, then run:")
    print(f"  python3 tools/expand_flags.py {auction_id}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    rows = DEFAULT_ROWS
    if "--rows" in argv:
        i = argv.index("--rows")
        try:
            rows = int(argv[i + 1])
        except (IndexError, ValueError):
            sys.exit("Error: --rows needs an integer")
        del argv[i:i + 2]
    if len(argv) != 1:
        sys.exit(__doc__)
    main(argv[0], rows)
