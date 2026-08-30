"""Tests for tools/split_passes.py — the flagging-pass partition.

The whole point of the split is that NOTHING is lost and nothing is judged
twice. These tests guard exactly that, plus the ordering trap that made the
first implementation send 100% of lots to the fallback pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from tools.split_passes import assign, load_passes

REPO_ROOT = Path(__file__).resolve().parents[2]
PASSES_YAML = REPO_ROOT / "passes.yaml"


def _passes():
    return load_passes(PASSES_YAML)


class TestAssign:
    def test_pass_a_wins_over_pass_b_prefix(self):
        """Pass A's prefixes live INSIDE pass B's "Home Goods & Decor".

        Order is load-bearing: if B were tested first it would swallow all of
        A, which is exactly what a hand-rolled prefix splitter did the first
        time (100% of lots landed in the fallback).
        """
        passes, fb = _passes()
        lot = {"category": "Home Goods & Decor - Home Goods - Bed / Bath Items"}
        assert assign(lot, passes, fb) == "A"

    def test_pass_b_takes_the_rest_of_home_goods(self):
        passes, fb = _passes()
        lot = {"category": "Home Goods & Decor - Home Goods - Small Appliances"}
        assert assign(lot, passes, fb) == "B"

    def test_tools_filed_under_lawn_and_garden_reach_pass_c(self):
        """HiBid files 59% of hand-tool inventory under Lawn & Garden."""
        passes, fb = _passes()
        assert assign({"category": "Lawn & Garden - Hand Tools"}, passes, fb) == "C"

    def test_missing_category_falls_back_not_dropped(self):
        passes, fb = _passes()
        assert assign({"category": None}, passes, fb) == fb
        assert assign({}, passes, fb) == fb
        assert assign({"category": "Some Category HiBid Invented"}, passes, fb) == fb


class TestPassesYaml:
    def test_every_focus_bucket_exists(self):
        passes, _ = _passes()
        names = {
            b["name"]
            for b in yaml.safe_load((REPO_ROOT / "buckets.yaml").read_text())["buckets"]
        }
        for spec in passes:
            unknown = [b for b in spec["focus_buckets"] if b not in names]
            assert not unknown, f"pass {spec['id']} names unknown buckets: {unknown}"

    def test_every_bucket_appears_in_some_focus_list(self):
        """A bucket in no focus list is invisible to every prompt's guidance."""
        passes, _ = _passes()
        names = {
            b["name"]
            for b in yaml.safe_load((REPO_ROOT / "buckets.yaml").read_text())["buckets"]
        }
        covered = {b for spec in passes for b in spec["focus_buckets"]}
        assert not (names - covered), f"buckets in no focus list: {sorted(names - covered)}"

    def test_fallback_names_a_real_pass(self):
        passes, fb = _passes()
        assert fb in {p["id"] for p in passes}


class TestPartitionIsExact:
    def test_every_lot_lands_in_exactly_one_pass(self, tmp_path):
        passes, fb = _passes()
        lots = [
            {"lot_number": "1", "category": "Home Goods & Decor - Home Goods - Bed / Bath Items"},
            {"lot_number": "2", "category": "Home Goods & Decor - Home Goods - Small Appliances"},
            {"lot_number": "3", "category": "Construction & Farm - Power Tools"},
            {"lot_number": "4", "category": "Toys - Dolls"},
            {"lot_number": "5", "category": None},
        ]
        seen = {}
        for lot in lots:
            pid = assign(lot, passes, fb)
            assert lot["lot_number"] not in seen
            seen[lot["lot_number"]] = pid
        assert len(seen) == len(lots)
        assert set(seen.values()) <= {p["id"] for p in passes}
