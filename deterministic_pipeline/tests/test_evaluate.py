import json
from pathlib import Path

import pytest

from deterministic_pipeline.classifier import Classification, DeterministicClassifier
from deterministic_pipeline.config import load_rules
from deterministic_pipeline.evaluate import (
    GoldError, evaluate, evaluate_gold, load_gold, passes_gates,
)

ROOT = Path(__file__).resolve().parents[2]


class StubClassifier:
    def classify(self, row):
        evidence = [{"kind": kind, "value": "fixture"}
                    for kind in row["expected_evidence_kinds"]]
        return Classification(
            row={"bats_buckets": row["actual_buckets"],
                 "bats_subtype": row.get("actual_subtype"),
                 "personal_match": row["actual_personal"]},
            provenance={"decisions": [{"decision": "matched", "matched_by": evidence}]})


def row(number, expected, actual, forbidden=()):
    return {
        "lot_number": str(number), "title": "Fixture product",
        "expected_buckets": list(expected), "forbidden_buckets": list(forbidden),
        "expected_subtype": None, "expected_evidence_kinds": ["title_seed"],
        "expected_personal": False, "critical_assertions": [],
        "rationale": "Human reviewed fixture rationale.",
        "actual_buckets": list(actual), "actual_subtype": None,
        "actual_personal": False,
    }


def test_evaluator_reports_bucket_and_forbidden_errors():
    rows = [row(1, ["Keyboard"], ["Keyboard"]),
            row(2, ["Tools"], ["Keyboard"], ["Keyboard"])]
    report = evaluate(rows, StubClassifier())
    assert report["micro_precision"] == 0.5
    assert report["micro_recall"] == 0.5
    assert report["violations"][0]["forbidden_matched"] == ["Keyboard"]
    passed, failures = passes_gates(report, [])
    assert passed is False
    assert any("forbidden" in failure for failure in failures)


def test_empty_and_inadequate_gold_cannot_certify(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"items": [], "rare_bucket_exemptions": {}}))
    with pytest.raises(GoldError, match="nonempty"):
        load_gold(empty)

    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    inadequate = tmp_path / "inadequate.json"
    fixture = {
        "items": [{
            "lot_number": "1", "title": "Mechanical keyboard",
            "condition": "Excellent",
            "expected_buckets": ["Keyboards & PC peripherals"],
            "forbidden_buckets": [], "expected_subtype": "mechanical keyboards",
            "expected_evidence_kinds": ["title_seed", "subtype_terms"],
            "expected_personal": False, "critical_assertions": ["keyboard"],
            "rationale": "Human reviewed keyboard positive.",
        }],
        "rare_bucket_exemptions": {},
    }
    inadequate.write_text(json.dumps(fixture))
    report = evaluate_gold(inadequate, rules)
    assert report["accuracy_gates_passed"] is False
    assert any("positive examples" in failure for failure in report["coverage_failures"])
    assert any("near-negative" in failure for failure in report["coverage_failures"])
    assert any("critical assertions" in failure for failure in report["coverage_failures"])


def test_rare_bucket_exemption_must_be_explicit_and_justified(tmp_path):
    rules = load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")
    path = tmp_path / "gold.json"
    path.write_text(json.dumps({
        "items": [{
            "lot_number": "1", "title": "Mechanical keyboard", "condition": "Excellent",
            "expected_buckets": ["Keyboards & PC peripherals"], "forbidden_buckets": [],
            "expected_subtype": "mechanical keyboards",
            "expected_evidence_kinds": ["title_seed"], "expected_personal": False,
            "critical_assertions": ["keyboard"], "rationale": "Reviewed example for testing.",
        }],
        "rare_bucket_exemptions": {"Smart locks": {"reason": "short", "min_positive": 1,
                                                    "min_negative": 1}},
    }))
    report = evaluate_gold(path, rules)
    assert any("justification" in failure for failure in report["coverage_failures"])
