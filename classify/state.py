"""Manifest and chunk lifecycle. All run state lives on disk.

Claude Code orchestrates but never holds the classified dataset: workers write
their own output files, this module validates them, and the parent process
only ever sees counts. That is the constraint the whole design turns on — the
flagging pass produces roughly 0.7M output tokens a week, which cannot be
relayed through an orchestrator's context.

Chunk states
------------
    pending      awaiting dispatch (fresh, or awaiting its one retry)
    ingested     validated; rows written to ingested/
    superseded   bisected; its children carry the work now
    blocked      exhausted retries and bisection — needs a human

Why retry-once-then-bisect rather than retry-until-clean
--------------------------------------------------------
Resending the same 500 lots to a fresh worker is worth exactly one attempt: it
clears transient flakiness. Beyond that the chunk itself is the problem, and
repeating it burns usage without converging. Halving isolates the offending
lots in log2 steps instead, and a chunk that still fails at the floor is
surfaced rather than retried forever.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from classify import chunking, config, prompts, provenance
from classify.validate import ChunkRejected, validate_output

# One clean retry before bisecting.
MAX_ATTEMPTS = 2
# Floor for bisection. Below this a failure is about the lots, not the size.
MIN_CHUNK = 25
MAX_DEPTH = 4

PENDING, INGESTED, SUPERSEDED, BLOCKED = "pending", "ingested", "superseded", "blocked"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PassRun:
    """One pass's working directory, manifest and chunk files."""

    def __init__(self, auction_id: str, pass_id: str) -> None:
        self.auction_id = auction_id
        self.pass_id = pass_id
        self.dir = config.work_dir(auction_id, pass_id)
        self.manifest_path = self.dir / "manifest.json"
        self.prompt_path = self.dir / "PROMPT.md"
        self.out_dir = self.dir / "out"
        self.ingested_dir = self.dir / "ingested"
        self.rejected_dir = self.dir / "rejected"
        self._data: dict | None = None

    # -- manifest ---------------------------------------------------------

    @property
    def data(self) -> dict:
        if self._data is None:
            if not self.manifest_path.exists():
                raise SystemExit(
                    f"Error: no manifest for pass {self.pass_id}. "
                    f"Run `python -m classify prepare {self.auction_id}` first."
                )
            self._data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return self._data

    def save(self) -> None:
        config.write_json(self.manifest_path, self.data, indent=2)

    @property
    def chunks(self) -> dict[str, dict]:
        return self.data["chunks"]

    def chunk_path(self, cid: str) -> Path:
        return self.dir / chunking.filename(cid)

    # -- prepare ----------------------------------------------------------

    def prepare(self, *, max_rows: int, max_bytes: int) -> dict:
        lots = config.load_items(
            config.pass_input_path(self.auction_id, self.pass_id),
            f"pass {self.pass_id} input",
        )
        prompt_text = prompts.build(self.pass_id, lots)
        parts = provenance.components(
            input_path=config.pass_input_path(self.auction_id, self.pass_id),
            prompt_text=prompt_text,
        )
        fp = provenance.fingerprint(parts)

        existing = None
        if self.manifest_path.exists():
            existing = json.loads(self.manifest_path.read_text(encoding="utf-8"))

        # A fingerprint change means something the results depend on moved.
        # Keeping prior chunks would blend two configurations, so they go.
        stale = bool(existing) and existing.get("fingerprint") != fp
        if stale:
            changed = [
                k for k, v in parts.items()
                if existing.get("components", {}).get(k) != v
            ]
            print(
                f"  pass {self.pass_id}: fingerprint changed ({', '.join(changed)}) "
                f"— discarding {sum(1 for c in existing['chunks'].values() if c['state'] == INGESTED)} "
                f"previously ingested chunks"
            )
            for sub in (self.out_dir, self.ingested_dir):
                if sub.exists():
                    shutil.rmtree(sub)

        for sub in (self.dir, self.out_dir, self.ingested_dir, self.rejected_dir):
            sub.mkdir(parents=True, exist_ok=True)
        self.prompt_path.write_text(prompt_text, encoding="utf-8")

        keep = {} if stale or not existing else existing["chunks"]
        pieces = chunking.split_rows(lots, max_rows=max_rows, max_bytes=max_bytes)

        chunks: dict[str, dict] = {}
        for i, piece in enumerate(pieces):
            cid = chunking.chunk_id(self.pass_id, i)
            config.write_json_rows(self.chunk_path(cid), piece)
            prior = keep.get(cid)
            if prior and prior.get("state") in (INGESTED, SUPERSEDED, BLOCKED):
                chunks[cid] = prior
            else:
                chunks[cid] = {
                    "state": PENDING,
                    "lots": [str(lot["lot_number"]) for lot in piece],
                    "attempts": prior.get("attempts", 0) if prior else 0,
                    "errors": [],
                    "warnings": [],
                    "parent": None,
                }
        # Children created by an earlier bisection are not regenerated by
        # split_rows; carry them across so their work is not lost.
        for cid, meta in keep.items():
            if cid not in chunks and meta.get("parent"):
                chunks[cid] = meta
                if not self.chunk_path(cid).exists():
                    meta["state"] = BLOCKED
                    meta["errors"] = ["chunk file missing after re-prepare"]

        self._data = {
            "auction_id": self.auction_id,
            "pass_id": self.pass_id,
            "pass_name": config.pass_spec(self.pass_id).get("name"),
            "prepared_at": _now(),
            "fingerprint": fp,
            "components": parts,
            "instructions": provenance.instruction_entries(),
            "bucket_count": len(config.load_buckets()),
            "input_lots": len(lots),
            "max_rows": max_rows,
            "max_bytes": max_bytes,
            "chunks": chunks,
        }
        self.save()
        return self._data

    # -- ingest -----------------------------------------------------------

    def _bisect(self, cid: str, meta: dict) -> list[str]:
        lots = config.load_items(self.chunk_path(cid), f"chunk {cid}")
        left, right = chunking.bisect(lots)
        created = []
        for child_cid, rows in zip(chunking.child_ids(cid), (left, right)):
            config.write_json_rows(self.chunk_path(child_cid), rows)
            self.chunks[child_cid] = {
                "state": PENDING,
                "lots": [str(r["lot_number"]) for r in rows],
                "attempts": 0,
                "errors": [],
                "warnings": [],
                "parent": cid,
            }
            created.append(child_cid)
        meta["state"] = SUPERSEDED
        meta["children"] = created
        return created

    def ingest(self) -> dict:
        known = {b["name"] for b in config.load_buckets()}
        profile = config.load_yaml(config.PROFILE_PATH)
        tag_vocab = {
            str(t).lower()
            for i in (profile.get("interests") or [])
            for t in (i.get("tags") or [])
        }
        bucket_count = self.data["bucket_count"]
        fp = self.data["fingerprint"]

        report = {"accepted": [], "rejected": [], "bisected": [], "blocked": []}

        for cid in sorted(self.chunks):
            meta = self.chunks[cid]
            if meta["state"] in (INGESTED, SUPERSEDED, BLOCKED):
                continue
            out_path = self.out_dir / chunking.filename(cid)
            if not out_path.exists():
                continue

            try:
                rows, warnings = validate_output(
                    out_path,
                    chunk_id=cid,
                    fingerprint=fp,
                    expected_lots=meta["lots"],
                    bucket_count=bucket_count,
                    known_buckets=known,
                    tag_vocab=tag_vocab,
                )
            except ChunkRejected as exc:
                meta["attempts"] += 1
                meta["errors"] = exc.errors
                # Keep the evidence: a rejected output is the only record of
                # what the worker actually produced.
                self.rejected_dir.mkdir(parents=True, exist_ok=True)
                out_path.replace(
                    self.rejected_dir
                    / f"{chunking.filename(cid)}.attempt{meta['attempts']}"
                )
                if meta["attempts"] < MAX_ATTEMPTS:
                    meta["state"] = PENDING
                    report["rejected"].append((cid, exc.errors))
                elif (
                    chunking.depth(cid) < MAX_DEPTH
                    and len(meta["lots"]) > MIN_CHUNK
                ):
                    report["bisected"].append((cid, self._bisect(cid, meta)))
                else:
                    meta["state"] = BLOCKED
                    report["blocked"].append((cid, exc.errors))
                continue

            config.write_json(self.ingested_dir / chunking.filename(cid), rows)
            meta["state"] = INGESTED
            meta["errors"] = []
            meta["warnings"] = warnings
            meta["ingested_at"] = _now()
            report["accepted"].append((cid, len(rows), warnings))

        self.save()
        return report

    # -- status / finalize -------------------------------------------------

    def is_stale(self) -> tuple[bool, list[str]]:
        """Whether the manifest's fingerprint still matches the current inputs."""
        lots = config.load_items(
            config.pass_input_path(self.auction_id, self.pass_id),
            f"pass {self.pass_id} input",
        )
        parts = provenance.components(
            input_path=config.pass_input_path(self.auction_id, self.pass_id),
            prompt_text=prompts.build(self.pass_id, lots),
        )
        stored = self.data["components"]
        changed = [k for k, v in parts.items() if stored.get(k) != v]
        return bool(changed), changed

    def covered_lots(self) -> set[str]:
        return {
            lot
            for meta in self.chunks.values()
            if meta["state"] == INGESTED
            for lot in meta["lots"]
        }

    def all_lots(self) -> set[str]:
        return {
            lot
            for meta in self.chunks.values()
            if meta["state"] != SUPERSEDED
            for lot in meta["lots"]
        }

    def dispatchable(self) -> list[str]:
        return sorted(c for c, m in self.chunks.items() if m["state"] == PENDING)

    def blocked(self) -> list[str]:
        return sorted(c for c, m in self.chunks.items() if m["state"] == BLOCKED)

    def rows(self) -> list[dict]:
        out: list[dict] = []
        for cid in sorted(self.chunks):
            if self.chunks[cid]["state"] != INGESTED:
                continue
            path = self.ingested_dir / chunking.filename(cid)
            out.extend(json.loads(path.read_text(encoding="utf-8")))
        return out

    def finalize(self) -> Path:
        missing = self.all_lots() - self.covered_lots()
        if missing:
            raise SystemExit(
                f"Error: pass {self.pass_id} has {len(missing)} lots unaccounted for "
                f"(e.g. {sorted(missing)[:5]}). Refusing to write a short file — "
                f"run `python -m classify status {self.auction_id}` and finish the "
                f"outstanding chunks first."
            )
        rows = self.rows()
        seen = {r["lot_number"] for r in rows}
        expected = self.all_lots()
        if seen != expected:
            raise SystemExit(
                f"Error: pass {self.pass_id} row set does not match its lot set "
                f"({len(seen)} rows vs {len(expected)} lots)"
            )
        path = config.flags_output_path(self.auction_id, self.pass_id)
        config.write_json(path, rows)
        return path
