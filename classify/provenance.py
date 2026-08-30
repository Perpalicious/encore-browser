"""Run fingerprints, so a resumed run cannot blend incompatible results.

`tools/verify_passes.py` already stamps a `lot_set_sha` that catches a stale
*lot set* — last week's file sitting at this week's path. That is the failure
that has actually bitten this project, but it is not the only one available to
an automated run. Results can also be blended across a `buckets.yaml` edit, a
prompt change, a contract change, or — the one that is invisible from inside
the repo — two machines whose Claude instruction files differ.

So every chunk records the fingerprint it was produced under, and `ingest`
refuses anything that no longer matches.

The instruction hierarchy is the subtle part
--------------------------------------------
A worker inherits a stack of instruction files, not just the repo's CLAUDE.md.
Two rules make that stack comparable across machines:

1. Hash content, never absolute paths. This repo lives at
   ~/projects/encore-browser on one machine and ~/code/encore-browser on the
   other; hashing paths would make every cross-machine run look stale for a
   reason that has nothing to do with behaviour.
2. Absence is part of the hash. A user-level CLAUDE.md present on one machine
   and missing on the other must change the fingerprint — that divergence is
   precisely what this is here to catch.

The manifest keeps the full resolved list (role, path, sha) so a mismatch can
be diagnosed down to the offending file; only the (role, sha) pairs are hashed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from classify import config
from classify.contract import CONTRACT_VERSION

# Pinned exactly, not the generic `sonnet` alias: a run must not be resumable
# against a different model, and an alias that later repoints must change the
# fingerprint rather than silently changing the workers.
MODEL_ID = "claude-sonnet-5"

ABSENT = "<absent>"

# `@path` on its own line is CLAUDE.md's import syntax. Bounded depth and a
# visited set keep a self-referential import from spinning.
_IMPORT_RE = re.compile(r"^\s*@([^\s]+)\s*$", re.MULTILINE)
_MAX_IMPORT_DEPTH = 3

# Directories that cannot contain instructions we care about but are expensive
# or noisy to walk.
_SKIP_DIRS = {".git", "node_modules", "data", "dist", "__pycache__",
              ".pytest_cache", "viewer", ".venv", "encore_lot_browser.egg-info"}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def sha_file(path: Path) -> str:
    """Content sha, or the ABSENT sentinel — absence must be hashable."""
    if not path.exists() or not path.is_file():
        return ABSENT
    return sha_bytes(path.read_bytes())


def _imports_from(path: Path, depth: int, seen: set[Path]) -> list[tuple[str, Path]]:
    if depth >= _MAX_IMPORT_DEPTH or not path.exists() or not path.is_file():
        return []
    out: list[tuple[str, Path]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    for raw in _IMPORT_RE.findall(text):
        target = Path(raw).expanduser()
        if not target.is_absolute():
            target = (path.parent / target).resolve()
        if target in seen or not target.exists():
            continue
        seen.add(target)
        label = f"import:{sha_bytes(str(target).encode())}"
        out.append((label, target))
        out.extend(_imports_from(target, depth + 1, seen))
    return out


def instruction_sources() -> list[tuple[str, Path]]:
    """The effective instruction stack a worker inherits, in a stable order.

    Roles are machine-independent labels; the absolute path travels alongside
    for diagnosis only and never enters the hash.
    """
    home = Path.home()
    root = config.REPO_ROOT
    sources: list[tuple[str, Path]] = [
        ("user:CLAUDE.md", home / ".claude" / "CLAUDE.md"),
        ("user:settings.json", home / ".claude" / "settings.json"),
        ("project:CLAUDE.md", root / "CLAUDE.md"),
        ("project:settings.json", root / ".claude" / "settings.json"),
        ("project:settings.local.json", root / ".claude" / "settings.local.json"),
    ]

    # Directory-scoped CLAUDE.md files anywhere in the repo. Sorted by
    # repo-relative path so the order is identical on both machines.
    nested: list[tuple[str, Path]] = []
    for found in root.rglob("CLAUDE.md"):
        if found == root / "CLAUDE.md":
            continue
        rel = found.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        nested.append((f"project:{rel.as_posix()}", found))
    sources.extend(sorted(nested))

    seen = {p.resolve() for _, p in sources if p.exists()}
    imported: list[tuple[str, Path]] = []
    for _, path in list(sources):
        imported.extend(_imports_from(path, 0, seen))
    sources.extend(sorted(imported))
    return sources


def instruction_entries() -> list[dict]:
    """Resolved instruction stack: role, path (diagnosis only), sha."""
    return [
        {"role": role, "path": str(path), "sha": sha_file(path)}
        for role, path in instruction_sources()
    ]


def instructions_sha(entries: list[dict] | None = None) -> str:
    entries = entries if entries is not None else instruction_entries()
    payload = json.dumps(
        [[e["role"], e["sha"]] for e in entries], separators=(",", ":")
    )
    return sha_bytes(payload.encode())


def components(*, input_path: Path, prompt_text: str) -> dict[str, str]:
    """Everything a chunk's validity depends on."""
    entries = instruction_entries()
    return {
        "input_sha": sha_file(input_path),
        "prompt_sha": sha_bytes(prompt_text.encode("utf-8")),
        "buckets_sha": sha_file(config.BUCKETS_PATH),
        "profile_sha": sha_file(config.PROFILE_PATH),
        "passes_sha": sha_file(config.PASSES_PATH),
        "contract_version": CONTRACT_VERSION,
        "worker_sha": sha_file(config.WORKER_PATH),
        "instructions_sha": instructions_sha(entries),
        "model": MODEL_ID,
    }


def fingerprint(parts: dict[str, str]) -> str:
    return sha_bytes(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode())
