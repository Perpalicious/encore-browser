"""Paths and small loaders shared across the classify commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

BUCKETS_PATH = REPO_ROOT / "buckets.yaml"
PROFILE_PATH = REPO_ROOT / "profile.yaml"
PASSES_PATH = REPO_ROOT / "passes.yaml"
PROMPT_TEMPLATE_PATH = REPO_ROOT / "prompts" / "flagging.md"
PROMPT_CAND_PATH = REPO_ROOT / "prompts" / "flagging_cand.md"
PROMPTS_DOC_PATH = REPO_ROOT / "PROMPTS.md"
WORKER_PATH = REPO_ROOT / ".claude" / "agents" / "lot-classifier.md"

CATEGORIZED_DIR = REPO_ROOT / "data" / "categorized"

PASS_IDS = ("a", "b", "c", "d")


def pass_input_path(auction_id: str, pass_id: str) -> Path:
    return CATEGORIZED_DIR / f"auction_{auction_id}_pass_{pass_id}.json"


def flags_output_path(auction_id: str, pass_id: str) -> Path:
    return CATEGORIZED_DIR / f"auction_{auction_id}_flags_{pass_id}.json"


def work_dir(auction_id: str, pass_id: str) -> Path:
    """Where chunks, the prompt and worker output live for one pass.

    Under data/categorized/ so it inherits the existing gitignore and the
    retention sweep in CLAUDE.md, rather than becoming a new untracked
    directory nobody remembers to clear.
    """
    return CATEGORIZED_DIR / f"auction_{auction_id}_chunks" / pass_id


def load_items(path: Path, label: str) -> list[dict]:
    """Read a lot list, accepting both the bare-array and {items:[...]} shapes."""
    if not path.exists():
        raise SystemExit(f"Error: {label} not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise SystemExit(f"Error: {label} is not a JSON array or an object with 'items': {path}")


def load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_buckets() -> list[dict]:
    return load_yaml(BUCKETS_PATH).get("buckets") or []


def load_passes() -> tuple[list[dict], str]:
    data = load_yaml(PASSES_PATH)
    return (data.get("passes") or []), str(data.get("fallback") or "d")


def pass_spec(pass_id: str) -> dict:
    for spec in load_passes()[0]:
        if str(spec.get("id", "")).lower() == pass_id.lower():
            return spec
    raise SystemExit(f"Error: pass {pass_id!r} is not defined in {PASSES_PATH}")


def write_json(path: Path, payload: Any, *, indent: int | None = None) -> None:
    """Atomic write, matching merge_categorized's tmp+replace approach."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=indent, ensure_ascii=False), encoding="utf-8"
    )
    tmp.replace(path)


def write_json_rows(path: Path, rows: list) -> None:
    """Atomic write of a list, one row per line.

    Same JSON as ``write_json`` would produce, but with a newline between
    elements. Worker agents read chunks with a line-indexed Read tool: a
    single-line file cannot be paged past its truncation point, so a chunk
    serialised without newlines is only partially visible to the worker and
    silently loses every row after the cutoff.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    body = ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    tmp.write_text(f"[\n{body}\n]" if rows else "[]", encoding="utf-8")
    tmp.replace(path)
