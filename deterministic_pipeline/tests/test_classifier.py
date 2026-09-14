from pathlib import Path

import pytest

from deterministic_pipeline.classifier import DeterministicClassifier
from deterministic_pipeline.config import ConfigError, load_rules


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def classifier():
    return DeterministicClassifier(load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml"))


def classify(classifier, title, condition="Excellent", category="", **fields):
    return classifier.classify({"lot_number": "1", "title": title,
                                "condition": condition, "category": category, **fields})


def test_known_keyboard_boundaries_and_multilabel(classifier):
    keyboard = classify(classifier, "Razer mechanical gaming keyboard")
    assert "Keyboards & PC peripherals" in keyboard.row["bats_buckets"]
    assert keyboard.row["bats_subtype"] == "mechanical keyboards"

    mouse = classify(classifier, "Logitech G wireless mouse")
    assert "Keyboards & PC peripherals" in mouse.row["bats_buckets"]
    assert "Electronics" in mouse.row["bats_buckets"]

    tray = classify(classifier, "Under-desk keyboard tray by Razer")
    assert "Keyboards & PC peripherals" not in tray.row["bats_buckets"]
    decision = next(d for d in tray.provenance["decisions"]
                    if d["bucket"] == "Keyboards & PC peripherals")
    assert decision["decision"] == "excluded"

    mower = classify(classifier, "Universal mower ignition key switch")
    assert "Keyboards & PC peripherals" not in mower.row["bats_buckets"]


def test_subtype_requires_exact_product_evidence(classifier):
    gaming = classify(classifier, "Razer gaming keyboard")
    assert "Keyboards & PC peripherals" in gaming.row["bats_buckets"]
    assert "bats_subtype" not in gaming.row
    assert "subtype_not_proven" in gaming.provenance["unresolved"]

    combo = classify(classifier, "Wireless gaming keyboard and mouse combo")
    assert combo.row["bats_subtype"] == "kb+mouse combos"

    switches = classify(classifier, "Akko mechanical keyboard key switches")
    assert switches.row["bats_subtype"] == "key switches"


def test_broad_brand_alone_is_unresolved_not_a_positive(classifier):
    result = classify(classifier, "DEWALT logo t-shirt")
    assert "Power tools" not in result.row["bats_buckets"]
    assert "brand_without_product_type:Power tools" in result.provenance["unresolved"]


def test_category_can_supply_structured_evidence(classifier):
    result = classify(classifier, "MX MASTER 3S", category=(
        "Computers & Electronics - Computers - Peripherals - Keyboards / Mice"))
    assert "Keyboards & PC peripherals" in result.row["bats_buckets"]
    evidence = next(d for d in result.provenance["decisions"]
                    if d["bucket"] == "Keyboards & PC peripherals")
    assert any(e["kind"] == "category_prefix" for e in evidence["matched_by"])


def test_consumable_condition_gate_and_personal_gate(classifier):
    opened = classify(classifier, "Olaplex shampoo grocery lot", "Good")
    assert "Hair care products" not in opened.row["bats_buckets"]
    assert opened.row["personal_match"] is False
    sealed = classify(classifier, "Olaplex shampoo grocery lot", "Brand New - Sealed",
                      seal_intact=True)
    assert "Hair care products" in sealed.row["bats_buckets"]
    assert sealed.row["personal_match"] is True
    missing = classify(classifier, "Olaplex shampoo grocery lot", None)
    assert "Hair care products" not in missing.row["bats_buckets"]
    assert "missing_condition:Hair care products" in missing.provenance["unresolved"]


def test_personal_hard_gates_projects_and_resale_accessories(classifier):
    broken = classifier.classify({"lot_number": "1", "title": "bulk lot pool pump",
                                  "condition": "Excellent", "functional": "No"})
    assert broken.row["personal_match"] is False
    assert "personal_hard_gate:functional:No" in broken.provenance["unresolved"]

    project = classify(classifier, "Cordless power drill")
    assert any(e["kind"] == "active_project" for e in project.provenance["project_evidence"])

    vacuum = classify(classifier, "Shark WandVac handheld vacuum")
    assert vacuum.row["personal_match"] is True
    accessory = classify(classifier, "Shark WandVac replacement filter")
    assert accessory.row["personal_match"] is False
    assert any(value.startswith("proven_resale_accessory:")
               for value in accessory.provenance["unresolved"])

    shoes = classify(classifier, "Nike boots wholesale lot")
    assert shoes.row["personal_match"] is False
    assert "personal_hard_gate:shoe_size:not_configured" in shoes.provenance["unresolved"]

    generic = classify(classifier, "bulk lot USB cable")
    assert generic.row["personal_match"] is False
    assert any("generic_accessory" in value for value in generic.provenance["unresolved"])


@pytest.mark.parametrize("title", [
    "Anker USB cable bulk lot",
    "Razer keyboard cable bulk lot",
    "DeWalt charger bulk lot",
])
def test_generic_accessory_gate_overrides_brand_and_profile_evidence(classifier, title):
    result = classify(classifier, title)
    assert result.row["personal_match"] is False
    assert any(value.startswith("personal_hard_gate:generic_accessory:")
               for value in result.provenance["unresolved"])


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("damaged", True, "personal_hard_gate:damaged:true"),
    ("damage", "cracked", "personal_hard_gate:damage:reported"),
    ("missing_parts", "receiver", "personal_hard_gate:missing_parts:reported"),
])
def test_damage_gates_override_profile_evidence(classifier, field, value, reason):
    result = classify(classifier, "bulk lot pool pump", **{field: value})
    assert result.row["personal_match"] is False
    assert reason in result.provenance["unresolved"]


def test_description_text_cannot_create_a_positive(classifier):
    plain = {"lot_number": "1", "title": "Wooden shelf", "condition": "Excellent"}
    noisy = {**plain, "description": "Unrelated note mentions mechanical keyboard"}
    assert classifier.classify(plain).row == classifier.classify(noisy).row


def test_config_rejects_duplicate_bucket_names(tmp_path):
    import copy
    import yaml

    buckets = tmp_path / "buckets.yaml"
    profile = tmp_path / "profile.yaml"
    bucket_doc = yaml.safe_load((ROOT / "buckets.yaml").read_text())
    bucket_doc["buckets"].append(copy.deepcopy(bucket_doc["buckets"][0]))
    buckets.write_text(yaml.safe_dump(bucket_doc, sort_keys=False))
    profile.write_text((ROOT / "profile.yaml").read_text())
    with pytest.raises(ConfigError, match="duplicate bucket"):
        load_rules(buckets, profile)


def test_config_converts_malformed_yaml_and_top_level_types(tmp_path):
    buckets = tmp_path / "buckets.yaml"
    profile = tmp_path / "profile.yaml"
    buckets.write_text("- not-a-mapping\n")
    profile.write_text("interests: []\n")
    with pytest.raises(ConfigError, match="must be a mapping"):
        load_rules(buckets, profile)


def test_config_rejects_unsupported_rule_keys(tmp_path):
    import yaml

    buckets = tmp_path / "buckets.yaml"
    profile = tmp_path / "profile.yaml"
    document = yaml.safe_load((ROOT / "buckets.yaml").read_text())
    document["buckets"][0]["include_all"] = ["unsupported"]
    buckets.write_text(yaml.safe_dump(document, sort_keys=False))
    profile.write_text((ROOT / "profile.yaml").read_text())
    with pytest.raises(ConfigError, match="unsupported keys"):
        load_rules(buckets, profile)


@pytest.mark.parametrize(("mutation", "message"), [
    ("sizes", "unsupported keys"),
    ("includes", "both seeds and include_any"),
    ("excludes", "both exclude and exclude_any"),
])
def test_config_rejects_ambiguous_legacy_keys_and_unknown_sizes(tmp_path, mutation, message):
    import yaml

    buckets = tmp_path / "buckets.yaml"
    profile = tmp_path / "profile.yaml"
    bucket_doc = yaml.safe_load((ROOT / "buckets.yaml").read_text())
    profile_doc = yaml.safe_load((ROOT / "profile.yaml").read_text())
    if mutation == "sizes":
        profile_doc["sizes"]["unknown"] = "value"
    elif mutation == "includes":
        bucket_doc["buckets"][0]["include_any"] = ["keyboard"]
    else:
        target = next(rule for rule in bucket_doc["buckets"] if "exclude" in rule)
        target["exclude_any"] = ["cable"]
    buckets.write_text(yaml.safe_dump(bucket_doc, sort_keys=False))
    profile.write_text(yaml.safe_dump(profile_doc, sort_keys=False))
    with pytest.raises(ConfigError, match=message):
        load_rules(buckets, profile)
