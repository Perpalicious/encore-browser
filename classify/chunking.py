"""Split a pass into worker-sized chunks.

500 lots is both the default and the hard maximum. The limit is about bounding
attention decay, not about output truncation: 500 rows is roughly 30K output
tokens against a 128K ceiling, so truncation was never the binding constraint.
What actually went wrong in this project's history was recall degrading across
a long list — 5 of 77 KEYBOARD lots flagged, 4 of 36 storage bins — so nothing
here raises the ceiling.

The byte limit is what keeps a chunk readable by the worker in one pass. A
worker's Read tool truncates at roughly 25K tokens, which for dense JSON is
around 40-45 KB, so the old 150 KB guard let `prepare` emit chunks the worker
could only see the first ~40% of. Chunks are also written one row per line
(see config.write_json_rows) so a worker can page a chunk that does truncate;
a single-line chunk cannot be paged past its cutoff at all, and the rows past
it are invisible rather than merely deferred.
"""

from __future__ import annotations

import json
import re

MAX_ROWS = 500
MAX_BYTES = 70_000

_CHUNK_ID_RE = re.compile(r"^(?P<pass>[a-z]+)/(?P<index>\d+)(?P<suffix>(?:\.\d+)*)$")


def row_bytes(row: dict) -> int:
    return len(json.dumps(row, ensure_ascii=False).encode("utf-8"))


def split_rows(
    lots: list[dict], *, max_rows: int = MAX_ROWS, max_bytes: int = MAX_BYTES
) -> list[list[dict]]:
    """Partition lots on row boundaries. Order-preserving and lossless.

    A chunk closes when either limit is reached. A single row larger than
    max_bytes still gets its own chunk rather than being dropped or split —
    a row is the atomic unit here.
    """
    if max_rows < 1:
        raise ValueError("max_rows must be >= 1")
    if max_rows > MAX_ROWS:
        raise ValueError(
            f"max_rows {max_rows} exceeds the hard maximum {MAX_ROWS}; the cap "
            f"bounds attention decay and is not a tuning knob"
        )

    chunks: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for lot in lots:
        n = row_bytes(lot)
        if current and (len(current) >= max_rows or size + n > max_bytes):
            chunks.append(current)
            current, size = [], 0
        current.append(lot)
        size += n
    if current:
        chunks.append(current)
    return chunks


def chunk_id(pass_id: str, index: int) -> str:
    return f"{pass_id}/{index:03d}"


def child_ids(cid: str) -> tuple[str, str]:
    """The two ids a chunk bisects into."""
    return f"{cid}.0", f"{cid}.1"


def depth(cid: str) -> int:
    """How many times this chunk has been bisected. 0 for an original chunk."""
    m = _CHUNK_ID_RE.match(cid)
    if not m:
        raise ValueError(f"malformed chunk id: {cid!r}")
    return m.group("suffix").count(".")


def pass_of(cid: str) -> str:
    m = _CHUNK_ID_RE.match(cid)
    if not m:
        raise ValueError(f"malformed chunk id: {cid!r}")
    return m.group("pass")


def filename(cid: str) -> str:
    """Filesystem-safe name for a chunk id: 'a/007.1' -> 'chunk_007.1.json'."""
    m = _CHUNK_ID_RE.match(cid)
    if not m:
        raise ValueError(f"malformed chunk id: {cid!r}")
    return f"chunk_{m.group('index')}{m.group('suffix')}.json"


def bisect(lots: list[dict]) -> tuple[list[dict], list[dict]]:
    """Halve a chunk's lots, left-biased on an odd count."""
    mid = (len(lots) + 1) // 2
    return lots[:mid], lots[mid:]
