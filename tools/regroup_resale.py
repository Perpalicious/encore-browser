"""
Re-value only the lots whose resale grouping was wrong, keeping the rest.

    python3 tools/regroup_resale.py <ID> plan     # builds the fix-up chat
    python3 tools/regroup_resale.py <ID> apply    # merges its response

plan reads  data/categorized/auction_<ID>_for_agent.json        (current slim)
            data/categorized/auction_<ID>_resale_groups.json    (the grouping that was valued)
            data/categorized/auction_<ID>_resale_deduped.json   (its valuations)
     writes data/categorized/auction_<ID>_resale_fix.json         (the chat's input)
            data/categorized/auction_<ID>_resale_fix_groups.json  (its fan-out map)
            data/categorized/auction_<ID>_resale_fix_prompt.md    (its prompt)

apply reads the same plus auction_<ID>_resale_fix_deduped.json (the response)
      writes auction_<ID>_resale_deduped.json and _resale_groups.json, rebuilt
             on the corrected grouping, then re-runs tools/expand_resale.py so
             auction_<ID>_resale.json is what `build` should see. The original
             response is kept as auction_<ID>_resale_deduped_before_fix.json.

Why
---
`tools/slim_resale.py` groups on every field that moves the price, so a
valuation is only ever copied between lots that match on all of them. That
holds only if those fields were populated when it ran. On 2026-09-13 HiBid
changed its description format, `condition` parsed as None on every lot, and
the grouping silently collapsed to title-only: 2,051 groups mixed conditions
and 4,596 lots (16.4%) were priced off a representative in a different
condition — 1,264 of them across the good/bad line (a FOR PARTS ONLY unit
valued as EXCELLENT, or the reverse).

The per-row valuations were fine — the model saw the grading in the
`description` field — so the wasteful fix is re-running the whole pass. A
valuation for representative R is still true for every lot whose *corrected*
group key equals R's corrected key. This tool regroups on the corrected slim,
keeps every valuation that still holds, and sends only the groups with no
valid valuation to one much smaller chat (~2,900 rows instead of ~18,000).

The same mechanism is what "reuse last week's valuations" would need
(CLAUDE.md, retention section): a valuation keyed on the corrected group key
is reusable wherever that key recurs.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

try:
    from tools import expand_resale, render_prompts
    from tools.slim_resale import group_key
except ImportError:  # run directly as `python3 tools/<script>.py`
    import expand_resale
    import render_prompts
    from slim_resale import group_key

OUT_DIR = Path("data/categorized")


def _load(path: Path, label: str):
    if not path.exists():
        sys.exit(f"Error: {label} not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _regroup(auction_id: str):
    """Corrected groups, plus which of them an existing valuation still covers.

    Returns (new_groups, reusable, valued_by_rep) where new_groups maps each
    corrected group key to its members (lot dicts, sorted by lot_number),
    reusable maps a group key to the old representative whose valuation still
    holds for it, and valued_by_rep maps old representatives to valuations.
    """
    slim = _load(OUT_DIR / f"auction_{auction_id}_for_agent.json", "slimmed file")
    old_groups = _load(OUT_DIR / f"auction_{auction_id}_resale_groups.json", "group map")
    valued = expand_resale.load_items(
        OUT_DIR / f"auction_{auction_id}_resale_deduped.json", "deduped resale file")
    valued_by_rep = {str(v.get("lot_number") or "").strip(): v for v in valued}

    by_lot = {str(r["lot_number"]): r for r in slim}
    new_groups: dict[tuple, list[dict]] = defaultdict(list)
    for rec in slim:
        new_groups[group_key(rec)].append(rec)
    for members in new_groups.values():
        members.sort(key=lambda r: str(r.get("lot_number")))

    # A valuation still holds for a group when its representative, keyed on
    # the corrected data, lands in that group.
    reusable: dict[tuple, str] = {}
    for rep in old_groups:
        if rep in by_lot and rep in valued_by_rep:
            reusable.setdefault(group_key(by_lot[rep]), rep)

    return new_groups, reusable, valued_by_rep


def plan(auction_id: str) -> None:
    new_groups, reusable, _ = _regroup(auction_id)

    fix_rows, fix_groups = [], {}
    for key, members in new_groups.items():
        if key in reusable:
            continue
        rep = dict(members[0])
        rep["qty"] = len(members)
        fix_rows.append(rep)
        fix_groups[str(rep["lot_number"])] = [str(m["lot_number"]) for m in members]
    fix_rows.sort(key=lambda r: str(r["lot_number"]))

    total = sum(len(m) for m in new_groups.values())
    covered = sum(len(v) for v in fix_groups.values())
    print(f"{total} lots -> {len(new_groups)} distinct products on the corrected grouping")
    print(f"  {len(new_groups) - len(fix_rows)} still covered by an existing valuation")
    print(f"  {len(fix_rows)} need valuing, covering {covered} lots "
          f"({100 * covered / total:.1f}% of the auction)")
    if not fix_rows:
        print("  nothing to do — every corrected group already has a valid valuation")
        return

    src = OUT_DIR / f"auction_{auction_id}_resale_fix.json"
    src.write_text(json.dumps(fix_rows), encoding="utf-8")
    groups_path = OUT_DIR / f"auction_{auction_id}_resale_fix_groups.json"
    groups_path.write_text(json.dumps(fix_groups), encoding="utf-8")
    prompt_path = OUT_DIR / f"auction_{auction_id}_resale_fix_prompt.md"
    prompt_path.write_text(render_prompts.render("resale.md", {
        "INPUT_FILE": src.name,
        "OUTPUT_FILE": f"auction_{auction_id}_resale_fix_deduped.json",
        "N": f"{len(fix_rows):,}",
        "LAST_LOT": str(fix_rows[-1]["lot_number"]),
    }), encoding="utf-8")
    print(f"  wrote {src}")
    print(f"  wrote {groups_path}")
    print()
    print("Resale fix-up (1 chat), attach NO config files:")
    print(f"  paste  {prompt_path}")
    print(f"  attach {src}")
    print(f"  save   {OUT_DIR / f'auction_{auction_id}_resale_fix_deduped.json'}")
    print(f"then: python3 tools/regroup_resale.py {auction_id} apply")


def apply(auction_id: str) -> None:
    new_groups, reusable, valued_by_rep = _regroup(auction_id)
    fix_groups = _load(OUT_DIR / f"auction_{auction_id}_resale_fix_groups.json",
                       "fix group map (run `plan` first)")
    fixed = expand_resale.load_items(
        OUT_DIR / f"auction_{auction_id}_resale_fix_deduped.json", "fix-up response")
    fixed_by_rep = {str(v.get("lot_number") or "").strip(): v for v in fixed}

    unknown = [k for k in fixed_by_rep if k not in fix_groups]
    if unknown:
        print(f"  WARNING: {len(unknown)} fix-up valuations had a lot_number not in "
              f"the fix plan and were ignored. First few: {unknown[:5]}", file=sys.stderr)

    merged, groups_out, missing = [], {}, []
    for key, members in new_groups.items():
        rep = str(members[0]["lot_number"])
        if key in reusable:
            valuation = dict(valued_by_rep[reusable[key]])
        elif rep in fixed_by_rep:
            valuation = dict(fixed_by_rep[rep])
        else:
            missing.append(rep)
            continue
        # Re-key on the corrected representative so the deduped file and
        # group map describe the same grouping.
        valuation["lot_number"] = rep
        merged.append(valuation)
        groups_out[rep] = [str(m["lot_number"]) for m in members]

    if missing:
        lost = sum(len(m) for k, m in new_groups.items() if str(m[0]["lot_number"]) in missing)
        sys.exit(f"\nError: {len(missing)} products in the fix plan were never valued, "
                 f"covering {lost} lots. The fix-up chat truncated — re-run it. Nothing "
                 f"written.\nFirst few: {missing[:10]}")

    deduped = OUT_DIR / f"auction_{auction_id}_resale_deduped.json"
    backup = deduped.with_name(f"auction_{auction_id}_resale_deduped_before_fix.json")
    if not backup.exists():
        shutil.copy(deduped, backup)
    deduped.write_text(json.dumps(merged), encoding="utf-8")
    (OUT_DIR / f"auction_{auction_id}_resale_groups.json").write_text(
        json.dumps(groups_out), encoding="utf-8")
    print(f"{len(merged)} valuations on the corrected grouping "
          f"({len(reusable)} kept, {len(merged) - len(reusable)} from the fix-up)")
    print(f"  original response kept at {backup}")
    print(f"  rewrote {deduped} and the group map; expanding:")
    expand_resale.main(auction_id)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in ("plan", "apply"):
        sys.exit(__doc__)
    {"plan": plan, "apply": apply}[sys.argv[2]](sys.argv[1])
