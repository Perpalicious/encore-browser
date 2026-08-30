"""Pin the contract to what the rest of the pipeline actually expects.

These are the tests that would catch the contract drifting away from
tools/prefilter.py, tools/verify_passes.py, or merge_categorized — the exact
class of mismatch that produces a complete, plausible, wrong bundle.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from classify import config, contract

REPO = Path(__file__).resolve().parents[2]


def _tools_module(name):
    sys.path.insert(0, str(REPO / "tools"))
    try:
        return __import__(name)
    finally:
        sys.path.pop(0)


def test_prefilter_uses_the_contract_base_row():
    assert _tools_module("prefilter").BASE_ROW is contract.BASE_ROW


def test_verify_passes_uses_the_contract_required_fields():
    assert _tools_module("verify_passes").REQUIRED is contract.REQUIRED_FIELDS


def test_base_row_matches_what_verify_passes_requires():
    """A non-match row must satisfy the categorized gate on its own, because
    merge_categorized replaces whole rows."""
    row = contract.base_row("S-1")
    assert contract.REQUIRED_FIELDS["categorized"] <= set(row)


def test_forbidden_keys_include_the_one_that_flips_transform_to_shape_b():
    assert "bats_category" in contract.FORBIDDEN_KEYS


def test_every_real_bucket_name_is_accepted_by_the_contract():
    names = [b["name"] for b in yaml.safe_load(
        (REPO / "buckets.yaml").read_text(encoding="utf-8"))["buckets"]]
    assert len(names) >= 60
    for name in names:
        row = contract.MatchRow(lot_number="S-1", is_bats_list=True,
                                bats_buckets=[name], personal_match=False,
                                bats_subtype="thing")
        assert row.bats_buckets == [name], "bucket names must survive verbatim"


def test_every_declared_subtype_fits_the_word_limit():
    """The contract's max-words guard must not reject buckets.yaml's own vocabulary."""
    buckets = yaml.safe_load((REPO / "buckets.yaml").read_text(encoding="utf-8"))["buckets"]
    for b in buckets:
        for s in (b.get("subtypes") or []):
            assert len(str(s).split()) <= contract.SUBTYPE_MAX_WORDS, (b["name"], s)


def test_every_profile_tag_is_accepted_as_a_personal_tag():
    profile = yaml.safe_load((REPO / "profile.yaml").read_text(encoding="utf-8"))
    tags = sorted({t for i in (profile.get("interests") or [])
                   for t in (i.get("tags") or [])})
    assert tags
    row = contract.MatchRow(lot_number="S-1", is_bats_list=False, bats_buckets=[],
                            personal_match=True, personal_tags=tags,
                            match_strength="strong", personal_reasoning="x")
    assert row.personal_tags == tags


def test_finalized_rows_merge_onto_a_base_file_with_zero_added(tmp_path):
    """CLAUDE.md step 5 requires `n_added == 0` on every chain. A flags file
    whose lot_numbers drifted from the base would show up here."""
    lots = [f"S-{i}" for i in range(1, 21)]
    base = {
        "lot_set_sha": "deadbeef",
        "source": "auction_test_for_agent.json",
        "items": [contract.base_row(l) for l in lots],
    }
    flags = [
        contract.MatchRow(lot_number="S-1", is_bats_list=True,
                          bats_buckets=["Hand tools"], personal_match=False,
                          bats_subtype="screwdrivers").to_row()
    ] + [contract.base_row(l) for l in lots[1:]]

    base_path, new_path, out_path = (tmp_path / n for n in
                                     ("base.json", "flags.json", "out.json"))
    base_path.write_text(json.dumps(base), encoding="utf-8")
    new_path.write_text(json.dumps(flags), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "merge_categorized",
         "--existing", str(base_path), "--new", str(new_path),
         "--output", str(out_path)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Merged 0 new items" in proc.stdout, proc.stdout

    merged = json.loads(out_path.read_text(encoding="utf-8"))
    items = merged["items"] if isinstance(merged, dict) else merged
    assert len(items) == 20
    assert merged.get("lot_set_sha") == "deadbeef", "envelope must survive the merge"
    flagged = [r for r in items if r["is_bats_list"]]
    assert len(flagged) == 1 and flagged[0]["bats_subtype"] == "screwdrivers"
