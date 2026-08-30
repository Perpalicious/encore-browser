"""Validate one worker's chunk output.

Split from contract.py because the checks here are about the *chunk* — did
every lot come back, is this the run we think it is — rather than about the
shape of a row. Row shape is contract.MatchRow's job.

Hard failures trigger retry and then bisection. Warnings are recorded and
surfaced by `status` but do not reject the chunk: they mirror what
`tools/verify_passes.py` already treats as informational (a subtype outside a
bucket's declared vocabulary, a personal_tag outside profile.yaml), and
rejecting on them would send chunks into bisection over wording.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from classify.contract import ChunkResponse, expand


class ChunkRejected(Exception):
    """A chunk output that cannot be accepted. `errors` is operator-facing."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _row_errors(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        out.append(f"{loc}: {err['msg']}")
    return out[:20]


def validate_output(
    path: Path,
    *,
    chunk_id: str,
    fingerprint: str,
    expected_lots: list[str],
    bucket_count: int,
    known_buckets: set[str],
    tag_vocab: set[str],
) -> tuple[list[dict], list[str]]:
    """Return (rows, warnings) or raise ChunkRejected.

    `rows` is every lot in the chunk as a full row — matches plus expanded
    no_match — ready to be written to the per-chunk ingested file.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ChunkRejected([f"not valid JSON: {exc}"]) from exc

    if not isinstance(raw, dict):
        raise ChunkRejected(
            [f"expected a JSON object with matches/no_match, got {type(raw).__name__}"]
        )

    try:
        response = ChunkResponse.model_validate(raw)
    except ValidationError as exc:
        raise ChunkRejected(_row_errors(exc)) from exc

    if response.chunk_id != chunk_id:
        errors.append(f"chunk_id {response.chunk_id!r} != expected {chunk_id!r}")

    # A mismatch here means the taxonomy, prompt, contract, worker definition
    # or instruction stack moved under the run. Reusing the result would blend
    # two different configurations into one bundle.
    if response.fingerprint != fingerprint:
        errors.append(
            f"fingerprint {response.fingerprint!r} != current {fingerprint!r} — "
            f"produced under a different configuration"
        )

    # The automated replacement for the manual "tell me how many buckets you
    # read" attachment check. Compared against the count parsed from
    # buckets.yaml at prepare time, never a hardcoded number.
    if response.buckets_seen != bucket_count:
        errors.append(
            f"buckets_seen {response.buckets_seen} != {bucket_count} in buckets.yaml — "
            f"the worker did not read the whole taxonomy"
        )

    matched = [m.lot_number for m in response.matches]
    returned = matched + list(response.no_match)
    expected = set(expected_lots)

    dupes = len(returned) - len(set(returned))
    if dupes:
        seen: set[str] = set()
        repeated = sorted({r for r in returned if r in seen or seen.add(r)})[:5]
        errors.append(f"{dupes} lot_numbers returned more than once (e.g. {repeated})")

    both = set(matched) & set(response.no_match)
    if both:
        errors.append(
            f"{len(both)} lots in both matches and no_match (e.g. {sorted(both)[:5]})"
        )

    missing = expected - set(returned)
    unknown = set(returned) - expected
    if missing:
        errors.append(
            f"{len(missing)} of {len(expected)} lots missing (e.g. {sorted(missing)[:5]})"
        )
    if unknown:
        errors.append(
            f"{len(unknown)} lot_numbers not in this chunk (e.g. {sorted(unknown)[:5]})"
        )

    # verify_passes.py hard-fails on unknown bucket names because they land in
    # a synthetic "Other" group in the viewer, so catch them here rather than
    # three steps later.
    stray_buckets = sorted(
        {b for m in response.matches for b in m.bats_buckets if b not in known_buckets}
    )
    if stray_buckets:
        errors.append(
            f"{len(stray_buckets)} bucket names are not in buckets.yaml: "
            f"{stray_buckets[:5]}"
        )

    if errors:
        raise ChunkRejected(errors)

    if tag_vocab:
        stray_tags = sorted(
            {
                t
                for m in response.matches
                for t in (m.personal_tags or [])
                if t.lower() not in tag_vocab
            }
        )
        if stray_tags:
            warnings.append(
                f"{len(stray_tags)} personal_tags outside profile.yaml: {stray_tags[:5]}"
            )

    long_subtypes = sorted(
        {
            m.bats_subtype
            for m in response.matches
            if m.bats_subtype and len(m.bats_subtype.split()) > 3
        }
    )
    if long_subtypes:
        warnings.append(
            f"{len(long_subtypes)} subtypes longer than 3 words: {long_subtypes[:3]}"
        )

    flagged = sum(1 for m in response.matches if m.is_bats_list)
    if flagged:
        multi = sum(1 for m in response.matches if len(m.bats_buckets) >= 2)
        if multi == 0 and flagged >= 20:
            warnings.append(
                f"{flagged} flagged lots, none with 2+ buckets — the known "
                f"one-bucket-per-lot failure mode"
            )

    return expand(response), warnings
