import json
from pathlib import Path

import pytest

from deterministic_pipeline.config import load_rules
from deterministic_pipeline.pipeline import PipelineError, load_items, process, run


ROOT = Path(__file__).resolve().parents[2]


def raw(lot_number, title, condition="Excellent"):
    return {"id": f"id-{lot_number}", "lot_number": lot_number, "title": title,
            "description": "", "description_raw": f"Condition: {condition}",
            "condition": condition,
            "hibid_category_path": "Computers & Electronics - Computers - Peripherals",
            "image_url": "https://example.test/image.jpg",
            "thumb_url": "https://example.test/thumb.jpg",
            "lot_url": f"https://encoreauctions.hibid.com/lot/{lot_number}/",
            "close_at": "2026-09-14T13:00:00-04:00"}


def test_pipeline_deduplicates_classification_and_fans_out_with_full_coverage():
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    items = [raw("2", "Govee LED light strip"), raw("1", "Govee LED light strip"),
             raw("3", "Plain wooden shelf")]
    categorized, provenance, report = process(items, rules)
    assert [row["lot_number"] for row in categorized] == ["1", "2", "3"]
    assert categorized[0]["bats_buckets"] == categorized[1]["bats_buckets"]
    assert len(categorized) == len(provenance) == 3
    assert report["distinct_products"] == 2
    assert report["exact_duplicates"] == 1
    assert report["design_guarantee"] == "classifier package contains no model or network client"
    assert "runtime_seconds" not in report
    assert "peak_rss_kib" not in report


def test_pipeline_is_deterministic_under_input_reordering():
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    items = [raw("2", "Govee LED strip"), raw("1", "Mechanical keyboard")]
    first = process(items, rules)[:2]
    second = process(list(reversed(items)), rules)[:2]
    assert first == second


def test_full_process_preserves_structured_fields_for_matching_and_gates():
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    item = raw("1", "SKU 123")
    item.pop("hibid_category_path")
    item.update({
        "category_path": ["Computers & Electronics", "Computers", "Peripherals"],
        "model": "Mechanical keyboard", "size": "M", "notes": "bulk lot",
        "functional": "No", "missing_parts": "receiver", "damage": "cracked",
        "damaged": True, "missing_major_parts": "Yes",
    })
    categorized, provenance, _ = process([item], rules)
    assert "Keyboards & PC peripherals" in categorized[0]["bats_buckets"]
    assert categorized[0]["personal_match"] is False
    assert "personal_hard_gate:functional:No" in provenance[0]["unresolved"]
    assert "personal_hard_gate:missing_major_parts:Yes" in provenance[0]["unresolved"]
    assert "personal_hard_gate:damaged:true" in provenance[0]["unresolved"]
    assert "personal_hard_gate:damage:reported" in provenance[0]["unresolved"]
    assert "personal_hard_gate:missing_parts:reported" in provenance[0]["unresolved"]


def test_full_process_accessory_gate_overrides_profile_evidence():
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    items = [raw(str(index), title) for index, title in enumerate((
        "Anker USB cable bulk lot", "Razer keyboard cable bulk lot",
        "DeWalt charger bulk lot"), start=1)]
    categorized, provenance, _ = process(items, rules)
    assert all(row["personal_match"] is False for row in categorized)
    assert all(any(reason.startswith("personal_hard_gate:generic_accessory:")
                   for reason in record["unresolved"]) for record in provenance)


def test_full_process_requires_explicit_seal_for_consumable_personal_pick():
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    unproven = raw("1", "Olaplex shampoo grocery lot", "Brand New - Sealed")
    proven = raw("2", "Olaplex shampoo grocery lot", "Brand New - Sealed")
    proven["seal_intact"] = True
    categorized, provenance, _ = process([unproven, proven], rules)
    by_lot = {row["lot_number"]: row for row in categorized}
    assert by_lot["1"]["personal_match"] is False
    assert by_lot["2"]["personal_match"] is True
    assert "personal_consumable_seal_unproven" in provenance[0]["unresolved"]


def test_pipeline_rejects_duplicate_lot_numbers():
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    with pytest.raises(PipelineError, match="duplicate lot_number"):
        process([raw("1", "Keyboard"), raw("1", "Mouse")], rules)


def test_reference_is_labeled_as_legacy_agreement_not_accuracy():
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    _, _, report = process([raw("1", "Mechanical keyboard")], rules,
                           {"1": {"Keyboards & PC peripherals"}})
    comparison = report["reference_comparison"]
    assert comparison["source"] == "legacy labels; not human ground truth"
    assert comparison["joined_lots"] == 1


def test_saved_scrape_to_build_bundle_has_no_generated_resale(tmp_path):
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps({"items": [raw("1", "Mechanical keyboard"),
                                                   raw("2", "Plain wooden shelf")]}))
    categorized = tmp_path / "categorized.json"
    provenance = tmp_path / "provenance.json"
    report = tmp_path / "report.json"
    markdown = tmp_path / "report.md"
    bundle = tmp_path / "bundle.json"
    result = run(raw_path=raw_path, categorized_path=categorized,
                 provenance_path=provenance, report_path=report,
                 markdown_path=markdown, performance_path=tmp_path / "performance.json",
                 rules=rules, bundle_path=bundle,
                 buckets_path=ROOT / "buckets.yaml")
    built = json.loads(bundle.read_text())
    assert result["valid_lots"] == 2
    assert len(built["lots"]) == 2
    assert all(lot["est_resale_low"] is None for lot in built["lots"])
    assert json.loads(categorized.read_text())[0]["lot_number"] == "1"
    assert json.loads(provenance.read_text())[0]["ruleset"] == rules.ruleset


def test_failed_build_leaves_all_run_outputs_unchanged(tmp_path, monkeypatch):
    import subprocess

    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps({"items": [raw("1", "Mechanical keyboard")]}))
    outputs = [tmp_path / name for name in
               ("categorized.json", "provenance.json", "report.json", "report.md", "performance.json")]
    for output in outputs:
        output.write_text("original")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess(a, 1, "build out", "build error"))
    with pytest.raises(PipelineError, match="bundle build failed"):
        run(raw_path=raw_path, categorized_path=outputs[0], provenance_path=outputs[1],
            report_path=outputs[2], markdown_path=outputs[3], performance_path=outputs[4],
            rules=rules, bundle_path=tmp_path / "bundle.json", buckets_path=ROOT / "buckets.yaml")
    assert [output.read_text() for output in outputs] == ["original"] * len(outputs)
    assert not (tmp_path / "bundle.json").exists()


def test_input_schema_rejects_malformed_rows(tmp_path):
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"items": [{"lot_number": 1, "title": "Keyboard"}]}))
    with pytest.raises(PipelineError, match="lot_number"):
        load_items(path)


def test_bundle_bytes_are_stable_for_reordered_equivalent_input(tmp_path):
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    items = [raw("2", "Govee LED strip"), raw("1", "Mechanical keyboard")]
    bundles = []
    for index, ordered in enumerate((items, list(reversed(items)))):
        root = tmp_path / str(index)
        raw_path = root / "raw.json"
        raw_path.parent.mkdir()
        raw_path.write_text(json.dumps({"items": ordered}))
        bundle = root / "bundle.json"
        run(raw_path=raw_path, categorized_path=root / "categorized.json",
            provenance_path=root / "provenance.json", report_path=root / "report.json",
            markdown_path=root / "report.md", performance_path=root / "performance.json",
            rules=rules, bundle_path=bundle, buckets_path=ROOT / "buckets.yaml")
        bundles.append(bundle.read_bytes())
    assert bundles[0] == bundles[1]
