"""Chunk the flagging passes, validate worker output, assemble the result.

    python -m classify prepare  <ID> [--pass a|b|c|d] [--chunk-size N] [--chunk-max-bytes N]
    python -m classify ingest   <ID> [--pass ...]
    python -m classify status   <ID> [--pass ...]
    python -m classify finalize <ID> [--pass ...]

`prepare` is re-runnable and keeps valid work; `finalize` refuses to write a
short file. See docs/PASS_SOURCES.md for what each pass reads, and CLAUDE.md
step 4 for where this sits in the weekly run.
"""

from __future__ import annotations

import argparse
import sys

from classify import chunking, config
from classify.state import BLOCKED, INGESTED, PENDING, SUPERSEDED, PassRun


def _runs(args) -> list[PassRun]:
    ids = [args.pass_id] if args.pass_id else list(config.PASS_IDS)
    return [PassRun(args.auction_id, p) for p in ids]


def cmd_prepare(args) -> int:
    total = 0
    for run in _runs(args):
        data = run.prepare(max_rows=args.chunk_size, max_bytes=args.chunk_max_bytes)
        n = len(data["chunks"])
        total += n
        pending = sum(1 for m in data["chunks"].values() if m["state"] == PENDING)
        print(
            f"pass {run.pass_id}  {data['input_lots']:>6} lots  {n:>3} chunks  "
            f"{pending:>3} pending  fingerprint {data['fingerprint']}"
        )
    print(f"\n{total} chunks total. Next: dispatch them, then `python -m classify ingest {args.auction_id}`.")
    print(f"`python -m classify status {args.auction_id}` prints the dispatch list.")
    return 0


def cmd_ingest(args) -> int:
    for run in _runs(args):
        report = run.ingest()
        acc, rej = report["accepted"], report["rejected"]
        print(
            f"pass {run.pass_id}  +{len(acc)} accepted  {len(rej)} rejected  "
            f"{len(report['bisected'])} bisected  {len(report['blocked'])} blocked"
        )
        for cid, n, warns in acc:
            for w in warns:
                print(f"    {cid}: warning — {w}")
        for cid, errs in rej:
            print(f"    {cid}: rejected, will retry once — {errs[0]}")
        for cid, kids in report["bisected"]:
            print(f"    {cid}: failed twice, bisected into {', '.join(kids)}")
        for cid, errs in report["blocked"]:
            print(f"    {cid}: BLOCKED — {'; '.join(errs)}")
    return 0


def cmd_status(args) -> int:
    incomplete = False
    dispatch: list[tuple[str, PassRun]] = []

    for run in _runs(args):
        stale, changed = run.is_stale()
        counts = {s: 0 for s in (PENDING, INGESTED, SUPERSEDED, BLOCKED)}
        for meta in run.chunks.values():
            counts[meta["state"]] += 1
        covered, all_lots = run.covered_lots(), run.all_lots()
        missing = all_lots - covered

        flag = "STALE" if stale else ("ok" if not missing else "incomplete")
        print(
            f"pass {run.pass_id}  {flag:11s} {len(covered):>6}/{len(all_lots):<6} lots  "
            f"pending {counts[PENDING]:>3}  ingested {counts[INGESTED]:>3}  "
            f"blocked {counts[BLOCKED]:>3}"
        )
        if stale:
            print(f"    fingerprint changed: {', '.join(changed)}")
            print(f"    re-run `python -m classify prepare {args.auction_id} --pass {run.pass_id}`")
            incomplete = True
        for cid in run.blocked():
            meta = run.chunks[cid]
            print(f"    BLOCKED {cid} ({len(meta['lots'])} lots): {'; '.join(meta['errors'])}")
            print(f"            lots: {', '.join(meta['lots'][:10])}"
                  f"{' ...' if len(meta['lots']) > 10 else ''}")
        if missing:
            incomplete = True
        for cid in run.dispatchable():
            dispatch.append((cid, run))

    if dispatch:
        print(f"\n=== DISPATCH ({len(dispatch)} chunks) ===")
        for cid, run in dispatch:
            meta = run.chunks[cid]
            print(
                f"{cid}\t{len(meta['lots'])}\t{run.chunk_path(cid)}\t"
                f"{run.out_dir / chunking.filename(cid)}\t{run.data['fingerprint']}\t"
                f"{run.prompt_path}"
            )
        print("(chunk_id, rows, input, output, fingerprint, prompt)")
    elif not incomplete:
        print(f"\nAll chunks ingested. Next: `python -m classify finalize {args.auction_id}`")

    return 1 if incomplete else 0


def cmd_finalize(args) -> int:
    written = []
    for run in _runs(args):
        stale, changed = run.is_stale()
        if stale:
            raise SystemExit(
                f"Error: pass {run.pass_id} is stale ({', '.join(changed)}). "
                f"Re-prepare and re-run it rather than shipping mixed results."
            )
        path = run.finalize()
        rows = run.rows()
        flagged = sum(1 for r in rows if r.get("is_bats_list"))
        picks = sum(1 for r in rows if r.get("personal_match") is True)
        multi = sum(1 for r in rows if len(r.get("bats_buckets") or []) >= 2)
        subtyped = sum(1 for r in rows if r.get("bats_subtype"))
        print(
            f"pass {run.pass_id}  {len(rows):>6} rows  {flagged:>5} flagged "
            f"({subtyped} subtyped, {multi} multi-bucket)  {picks:>4} picks  -> {path.name}"
        )
        written.append(path)

    if len(written) == len(config.PASS_IDS):
        print("\nNext: chain the four onto the base file (CLAUDE.md step 5).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="classify", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn, helptext in (
        ("prepare", cmd_prepare, "chunk the passes and write worker prompts"),
        ("ingest", cmd_ingest, "validate whatever workers have written so far"),
        ("status", cmd_status, "what is done, outstanding, stale or blocked"),
        ("finalize", cmd_finalize, "write _flags_<x>.json once every lot is accounted for"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("auction_id")
        p.add_argument("--pass", dest="pass_id", choices=config.PASS_IDS,
                       help="one pass only (default: all four)")
        if name == "prepare":
            p.add_argument("--chunk-size", type=int, default=chunking.MAX_ROWS,
                           help=f"lots per chunk (default and maximum {chunking.MAX_ROWS})")
            p.add_argument("--chunk-max-bytes", type=int, default=chunking.MAX_BYTES,
                           help=f"serialized ceiling per chunk (default {chunking.MAX_BYTES})")
        p.set_defaults(func=fn)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
