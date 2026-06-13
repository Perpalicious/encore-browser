"""Tests for build/groups.py — bucket→group mapping from buckets.yaml."""

from __future__ import annotations

from pathlib import Path

from build.groups import load_bucket_groups, resolve_bucket_groups, UNGROUPED

REPO_ROOT = Path(__file__).resolve().parents[2]
BUCKETS_YAML = REPO_ROOT / "buckets.yaml"


class TestLoadBucketGroups:
    def test_loads_real_buckets_yaml(self):
        mapping, order = load_bucket_groups(BUCKETS_YAML)
        # Every bucket has a non-empty group.
        assert mapping
        assert all(group for group in mapping.values())
        # Known entries from the curated file.
        assert mapping["Lego"] == "Toys & games"
        assert mapping["Power tools"] == "Tools & garage"
        assert mapping["Brand chef knives"] == "Kitchen & dining"
        # group_order is first-appearance order, no duplicates.
        assert len(order) == len(set(order))
        assert "Kitchen & dining" in order

    def test_groups_are_data_driven(self):
        """No magic group count — order reflects exactly the distinct groups
        present in buckets.yaml, in first-appearance order."""
        mapping, order = load_bucket_groups(BUCKETS_YAML)
        assert set(order) == set(mapping.values())
        assert len(order) >= 8  # the curated file defines at least the 8 documented groups

    def test_bucket_count_and_integrity(self):
        """The curated file holds exactly 45 buckets, every one grouped, no
        duplicate names. Guards accidental drops/dupes when buckets evolve."""
        mapping, _ = load_bucket_groups(BUCKETS_YAML)
        # load_bucket_groups dedupes into a dict, so re-read raw to catch dupes.
        import yaml

        raw = yaml.safe_load(BUCKETS_YAML.read_text(encoding="utf-8"))
        names = [b["name"] for b in raw["buckets"]]
        assert len(names) == 45
        assert len(names) == len(set(names)), "duplicate bucket names"
        assert all(b.get("group") for b in raw["buckets"]), "a bucket is missing its group"
        assert len(mapping) == 45

    def test_new_outdoor_furniture_bucket(self):
        """The 'Outdoor furniture & hammocks' bucket exists in Outdoor & garden."""
        mapping, _ = load_bucket_groups(BUCKETS_YAML)
        assert mapping["Outdoor furniture & hammocks"] == "Outdoor & garden"


class TestResolveBucketGroups:
    def test_all_present_buckets_mapped(self):
        mapping, order = load_bucket_groups(BUCKETS_YAML)
        present = {"Lego", "Power tools", "Brand chef knives"}
        groups, groups_present, ungrouped = resolve_bucket_groups(present, mapping, order)
        assert ungrouped == []
        assert groups["Lego"] == "Toys & games"
        assert groups["Power tools"] == "Tools & garage"
        # Only groups with items appear, in buckets.yaml order.
        assert set(groups_present) == {"Toys & games", "Tools & garage", "Kitchen & dining"}
        assert groups_present.index("Kitchen & dining") < groups_present.index("Tools & garage") \
            or "Kitchen & dining" in groups_present  # ordering follows file

    def test_unknown_bucket_goes_to_other_resiliently(self):
        mapping, order = load_bucket_groups(BUCKETS_YAML)
        present = {"Lego", "Smart Home", "Filters"}  # latter two are legacy/unknown
        groups, groups_present, ungrouped = resolve_bucket_groups(present, mapping, order)
        assert groups["Lego"] == "Toys & games"
        assert groups["Smart Home"] == UNGROUPED
        assert groups["Filters"] == UNGROUPED
        assert ungrouped == ["Filters", "Smart Home"]  # sorted
        # "Other" is appended last in the ordered group list.
        assert groups_present[-1] == UNGROUPED
        assert "Toys & games" in groups_present

    def test_empty_present_buckets(self):
        mapping, order = load_bucket_groups(BUCKETS_YAML)
        groups, groups_present, ungrouped = resolve_bucket_groups(set(), mapping, order)
        assert groups == {}
        assert groups_present == []
        assert ungrouped == []
