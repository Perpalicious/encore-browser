"""A miniature repo on disk, so state/prepare/ingest can be driven end to end.

The real buckets.yaml has 62 buckets; the fixture has 3 deliberately, so any
test that hardcodes 62 fails instead of passing by coincidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from classify import config

BUCKETS_YAML = """\
buckets:
  - name: "Hand tools"
    group: "Tools & garage"
    description: "Hand tools."
    subtypes: ["screwdrivers", "wrenches"]
  - name: "Board games"
    group: "Toys & games"
    description: "Board games."
    subtypes: ["board games"]
  - name: "Electronics"
    group: "Electronics & gaming"
    description: "Consumer electronics."
    subtypes: ["headphones"]
"""

PROFILE_YAML = """\
interests:
  - name: "Garage"
    buckets: ["Hand tools"]
    tags: ["diy", "garage"]
    description: "Workshop build-out."
"""

PASSES_YAML = """\
fallback: d
passes:
  - id: a
    name: "Test pass A"
    categories: ["Tools"]
    focus_buckets: ["Hand tools"]
  - id: b
    name: "Test pass B"
    categories: ["Toys"]
    focus_buckets: ["Board games"]
  - id: c
    name: "Test pass C"
    categories: ["Misc"]
    focus_buckets: []
  - id: d
    name: "Test pass D"
    categories: ["Other"]
    focus_buckets: ["Electronics"]
"""


def lot(n: int, **extra) -> dict:
    row = {
        "lot_number": f"S-{n}",
        "title": f"ITEM {n}",
        "est_retail_price": 10.0,
        "condition": "Good",
        "category": "Tools - Hand Tools",
    }
    row.update(extra)
    return row


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Point every config path at a temporary tree."""
    root = tmp_path / "repo"
    (root / "prompts").mkdir(parents=True)
    (root / "data" / "categorized").mkdir(parents=True)
    (root / ".claude" / "agents").mkdir(parents=True)

    (root / "buckets.yaml").write_text(BUCKETS_YAML, encoding="utf-8")
    (root / "profile.yaml").write_text(PROFILE_YAML, encoding="utf-8")
    (root / "passes.yaml").write_text(PASSES_YAML, encoding="utf-8")
    (root / "CLAUDE.md").write_text("# project instructions\n", encoding="utf-8")
    (root / ".claude" / "agents" / "lot-classifier.md").write_text(
        "---\nname: lot-classifier\n---\nclassify.\n", encoding="utf-8"
    )

    # Copy the real prompt assets so the tests exercise the shipped text.
    for name in ("flagging.md", "flagging_cand.md", "input_fields.md"):
        (root / "prompts" / name).write_text(
            (config.REPO_ROOT / "prompts" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    monkeypatch.setattr(config, "REPO_ROOT", root)
    monkeypatch.setattr(config, "BUCKETS_PATH", root / "buckets.yaml")
    monkeypatch.setattr(config, "PROFILE_PATH", root / "profile.yaml")
    monkeypatch.setattr(config, "PASSES_PATH", root / "passes.yaml")
    monkeypatch.setattr(config, "PROMPT_TEMPLATE_PATH", root / "prompts" / "flagging.md")
    monkeypatch.setattr(config, "PROMPT_CAND_PATH", root / "prompts" / "flagging_cand.md")
    monkeypatch.setattr(config, "WORKER_PATH", root / ".claude" / "agents" / "lot-classifier.md")
    monkeypatch.setattr(config, "CATEGORIZED_DIR", root / "data" / "categorized")
    return root


@pytest.fixture
def pass_a(repo):
    """A 12-lot pass A input."""
    lots = [lot(i) for i in range(1, 13)]
    config.write_json(config.pass_input_path("test", "a"), lots)
    return lots


def write_output(run, cid, *, matches=None, no_match=None, fingerprint=None,
                 buckets_seen=3, chunk_id=None):
    """Stand in for a worker writing its chunk result."""
    from classify import chunking

    payload = {
        "chunk_id": chunk_id if chunk_id is not None else cid,
        "fingerprint": fingerprint if fingerprint is not None else run.data["fingerprint"],
        "buckets_seen": buckets_seen,
        "matches": matches or [],
        "no_match": no_match if no_match is not None else list(run.chunks[cid]["lots"]),
    }
    run.out_dir.mkdir(parents=True, exist_ok=True)
    (run.out_dir / chunking.filename(cid)).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return payload
