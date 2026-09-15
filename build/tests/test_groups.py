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
        """The curated file holds exactly 72 buckets, every one grouped, no
        duplicate names. Guards accidental drops/dupes when buckets evolve.

        Bump this deliberately when a bucket is added or removed — a stale
        count here is the only thing that catches an accidental drop."""
        mapping, _ = load_bucket_groups(BUCKETS_YAML)
        # load_bucket_groups dedupes into a dict, so re-read raw to catch dupes.
        import yaml

        raw = yaml.safe_load(BUCKETS_YAML.read_text(encoding="utf-8"))
        names = [b["name"] for b in raw["buckets"]]
        # 2026-08-30: 48 -> 61. Added Personal care (6) and Food & drink (3
        # new), plus Vacuums & floor care, Seating & occasional furniture,
        # Car care & detailing, Lawn treatment & pest control, Kids' outdoor
        # water play, Kids' craft & activity, Audio & headphones. Folded
        # "Starbucks coffee" into
        # "Coffee & espresso" and "Shatterproof / outdoor dishware" into
        # "Dinnerware". See data/Watch/FINDINGS.md.
        # 2026-09-14: 62 -> 63. Split "Insulated drinkware" (Stanley, Owala,
        # Hydro Flask, S'well, Thermos...) out of "Glassware & drinkware",
        # which held ~180 insulated lots against ~20 of actual glass.
        # 2026-09-15: 63 -> 72. Bat's List narrowed to a targeted list (see the
        # SCOPE POLICY in buckets.yaml). Retired Electronics, Batteries &
        # chargers, Tarps, Sports & recreation gear; split Keyboards/PC
        # peripherals, Home gym, Vacuums (x3), Boots (adult/kids), Kitchen
        # appliances; added Monitors, Networking, Backyard games, Nets/goals,
        # Bikes, Pool & hot tub care, Playroom & active play.
        assert len(names) == 72
        assert len(names) == len(set(names)), "duplicate bucket names"
        assert all(b.get("group") for b in raw["buckets"]), "a bucket is missing its group"
        assert len(mapping) == 72

    def test_new_outdoor_furniture_bucket(self):
        """The 'Outdoor furniture & hammocks' bucket exists in Outdoor & garden."""
        mapping, _ = load_bucket_groups(BUCKETS_YAML)
        assert mapping["Outdoor furniture & hammocks"] == "Outdoor & garden"

    def test_keyboards_bucket_renamed_and_broadened(self):
        """"Mechanical keyboards" asked a question titles cannot answer — you
        cannot tell mechanical from membrane from "KLIM CHROMA WIRELESS GAMING
        KEYBOARD RGB" — so it hedged into Electronics or nothing. On
        2026-09-15 keyboards got their own bucket again (keycaps and switches
        included), mice moved to "PC peripherals", and the "Electronics"
        catch-all was retired."""
        mapping, _ = load_bucket_groups(BUCKETS_YAML)
        assert mapping["Keyboards, keycaps & switches"] == "Electronics & gaming"
        assert mapping["PC peripherals"] == "Electronics & gaming"
        assert "Mechanical keyboards" not in mapping
        assert "Keyboards & PC peripherals" not in mapping
        assert "Electronics" not in mapping

    def test_scope_narrowing_2026_09_15(self):
        """Bat's List was narrowed to a targeted list: zero-engagement
        catch-alls retired, the best buckets split so the wanted half is
        not buried. See SCOPE POLICY in buckets.yaml."""
        mapping, _ = load_bucket_groups(BUCKETS_YAML)
        for retired in ("Electronics", "Batteries & chargers", "Tarps",
                        "Sports & recreation gear", "Video games & VR",
                        "Kitchen appliances", "Brand boots & shoes",
                        "Home gym & weightlifting"):
            assert retired not in mapping, retired
        assert mapping["Handheld & cordless vacs"] == "Cleaning & storage"
        assert mapping["Robot vacuums & mops"] == "Cleaning & storage"
        assert mapping["Weights, bars & racks"] == "Sports & fitness"
        assert mapping["Gym accessories"] == "Sports & fitness"
        assert mapping["Brand shoes (adult)"] == "Footwear"
        assert mapping["Brand shoes (kids)"] == "Footwear"
        assert mapping["Pool & hot tub care"] == "Outdoor & garden"
        assert mapping["Playroom & active play"] == "Toys & games"
        assert mapping["VR headsets & accessories"] == "Electronics & gaming"

    def test_buckets_added_for_previously_unbucketed_picks(self):
        """Hand tools, dolls/plush and non-Starbucks coffee had no bucket, so
        picks in those areas landed nowhere in the viewer's nav.

        Coffee moved out of "Kitchen & dining" into its own "Food & drink"
        group on 2026-08-30 — the bucket still exists, which is what this
        guards; only its group changed."""
        mapping, _ = load_bucket_groups(BUCKETS_YAML)
        assert mapping["Hand tools"] == "Tools & garage"
        assert mapping["Dolls, plush & playsets"] == "Toys & games"
        assert mapping["Coffee & espresso"] == "Food & drink"
        # Folded-in buckets must be gone, not silently duplicated.
        assert "Starbucks coffee" not in mapping
        assert "Shatterproof / outdoor dishware" not in mapping

    def test_personal_care_and_food_groups_exist(self):
        """The two groups added from three months of bid/watch history.
        Personal care was ~840 lots/week of supply with no bucket at all."""
        mapping, order = load_bucket_groups(BUCKETS_YAML)
        assert mapping["Skincare & body"] == "Personal care"
        assert mapping["Hair styling tools"] == "Personal care"
        assert mapping["Snacks & confectionery"] == "Food & drink"
        assert mapping["Vacuums & floor care"] == "Cleaning & storage"
        assert "Personal care" in order and "Food & drink" in order


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
