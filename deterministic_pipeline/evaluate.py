"""Evaluate deterministic rules against an explicitly human-reviewed set."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .classifier import DeterministicClassifier
from .config import ConfigError, Rules, load_rules
from .normalize import normalize_text

MIN_POSITIVES = 20
MIN_NEGATIVES = 20
REQUIRED_CRITICAL = {"keyboard", "proven_resale", "personal_hard_gate"}
EVIDENCE_KINDS = {"title_seed", "category_prefix", "subtype_terms"}


class GoldError(ValueError):
    """The gold fixture is malformed or too small to certify a cutover."""


def load_gold(path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldError(f"cannot read valid gold JSON {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise GoldError("gold file must be an object with items and rare_bucket_exemptions")
    rows = document.get("items")
    exemptions = document.get("rare_bucket_exemptions", {})
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise GoldError("gold.items must be a nonempty list of objects")
    if not isinstance(exemptions, dict):
        raise GoldError("gold.rare_bucket_exemptions must be an object")
    return rows, exemptions


def validate_coverage(rows: list[dict[str, Any]], rules: Rules,
                      exemptions: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    known = {rule.name for rule in rules.buckets}
    positive: Counter[str] = Counter()
    negative: Counter[str] = Counter()
    subtype_covered: Counter[str] = Counter()
    critical: set[str] = set()
    seen_lots: set[str] = set()
    for index, row in enumerate(rows):
        lot = row.get("lot_number")
        if not isinstance(lot, str) or not lot.strip() or lot in seen_lots:
            failures.append(f"gold row {index} needs a unique nonempty string lot_number")
        else:
            seen_lots.add(lot)
        if not isinstance(row.get("title"), str) or not row["title"].strip():
            failures.append(f"gold row {index} needs a nonempty string title")
        for field in ("expected_buckets", "forbidden_buckets", "expected_evidence_kinds",
                      "critical_assertions"):
            value = row.get(field)
            if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
                failures.append(f"gold row {index}.{field} must be a list of nonempty strings")
            elif len(value) != len(set(value)):
                failures.append(f"gold row {index}.{field} contains duplicate values")
        expected = row.get("expected_buckets") if isinstance(row.get("expected_buckets"), list) else []
        forbidden = row.get("forbidden_buckets") if isinstance(row.get("forbidden_buckets"), list) else []
        unknown = (set(expected) | set(forbidden)) - known
        if unknown:
            failures.append(f"gold row {index} references unknown buckets: {sorted(unknown)}")
        positive.update(set(expected))
        negative.update(set(forbidden))
        if set(expected) & set(forbidden):
            failures.append(f"gold row {index} cannot expect and forbid the same bucket")
        evidence = set(row.get("expected_evidence_kinds") or [])
        if evidence - EVIDENCE_KINDS:
            failures.append(f"gold row {index} has unknown evidence kinds: {sorted(evidence - EVIDENCE_KINDS)}")
        assertions = set(row.get("critical_assertions") or [])
        if assertions - REQUIRED_CRITICAL:
            failures.append(f"gold row {index} has unknown critical assertions: {sorted(assertions - REQUIRED_CRITICAL)}")
        critical.update(assertions)
        if not isinstance(row.get("expected_personal"), bool):
            failures.append(f"gold row {index}.expected_personal must be boolean")
        if expected and "expected_subtype" not in row:
            failures.append(f"gold row {index} needs expected_subtype (string or null)")
        if row.get("expected_subtype") is not None and not isinstance(row.get("expected_subtype"), str):
            failures.append(f"gold row {index}.expected_subtype must be string or null")
        if expected and not row.get("expected_evidence_kinds"):
            failures.append(f"gold row {index} needs expected provenance evidence")
        expected_subtype = row.get("expected_subtype")
        if isinstance(expected_subtype, str):
            allowed_subtypes = {subtype for rule in rules.buckets if rule.name in expected
                                for subtype in rule.subtypes}
            if expected_subtype not in allowed_subtypes:
                failures.append(f"gold row {index} subtype is not controlled by an expected bucket")
            else:
                subtype_covered.update(expected)
        if "personal_hard_gate" in assertions:
            triggers_gate = (
                row.get("condition") in rules.personal_gates.reject_conditions
                or row.get("functional") in rules.personal_gates.reject_functional
                or row.get("missing_major_parts") in rules.personal_gates.reject_missing_major_parts
            )
            if row.get("expected_personal") is not False or not triggers_gate:
                failures.append(f"gold row {index} personal_hard_gate lacks a typed rejecting input")
        source_text = normalize_text(" ".join(str(row.get(field) or "") for field in
                                               ("title", "category", "hibid_category_path")))
        if "keyboard" in assertions and (
                "Keyboards & PC peripherals" not in expected or "keyboard" not in source_text):
            failures.append(f"gold row {index} keyboard assertion lacks source semantics/expected bucket")
        if "proven_resale" in assertions:
            resale_terms = {normalize_text(term.strip()) for product in rules.proven_resale
                            for term in product.include_any}
            if row.get("expected_personal") is not True or not any(
                    term and term in source_text for term in resale_terms):
                failures.append(f"gold row {index} proven_resale lacks source semantics/personal match")
        if not isinstance(row.get("rationale"), str) or len(row["rationale"].strip()) < 10:
            failures.append(f"gold row {index} needs a human rationale of at least 10 characters")

    unknown_exemptions = set(exemptions) - known
    if unknown_exemptions:
        failures.append(f"rare-bucket exemptions reference unknown buckets: {sorted(unknown_exemptions)}")
    for bucket in sorted(known):
        required_positive = MIN_POSITIVES
        required_negative = MIN_NEGATIVES
        if bucket in exemptions:
            exemption = exemptions[bucket]
            if not isinstance(exemption, dict):
                failures.append(f"{bucket} exemption must be an object")
                continue
            reason = exemption.get("reason")
            min_positive = exemption.get("min_positive")
            min_negative = exemption.get("min_negative")
            if not isinstance(reason, str) or len(reason.strip()) < 20:
                failures.append(f"{bucket} exemption needs a justification of at least 20 characters")
                continue
            if type(min_positive) is not int or not 1 <= min_positive < MIN_POSITIVES:
                failures.append(f"{bucket} exemption min_positive must be 1..{MIN_POSITIVES - 1}")
                continue
            if type(min_negative) is not int or not 1 <= min_negative < MIN_NEGATIVES:
                failures.append(f"{bucket} exemption min_negative must be 1..{MIN_NEGATIVES - 1}")
                continue
            required_positive, required_negative = min_positive, min_negative
        if positive[bucket] < required_positive:
            failures.append(f"{bucket} has {positive[bucket]}/{required_positive} positive examples")
        if negative[bucket] < required_negative:
            failures.append(f"{bucket} has {negative[bucket]}/{required_negative} near-negative examples")
        if subtype_covered[bucket] < 1:
            failures.append(f"{bucket} has no controlled subtype assertion")
    missing_critical = REQUIRED_CRITICAL - critical
    if missing_critical:
        failures.append(f"gold set lacks critical assertions: {sorted(missing_critical)}")
    return failures


def evaluate(rows: list[dict[str, Any]], classifier: DeterministicClassifier) -> dict[str, Any]:
    tp = fp = fn = 0
    per_bucket: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    violations: list[dict[str, Any]] = []
    personal_correct = 0
    for index, source in enumerate(rows):
        expected = set(source["expected_buckets"])
        forbidden = set(source["forbidden_buckets"])
        classification = classifier.classify(source)
        result = classification.row
        actual = set(result["bats_buckets"])
        tp += len(actual & expected)
        fp += len(actual - expected)
        fn += len(expected - actual)
        for name in actual & expected:
            per_bucket[name][0] += 1
        for name in actual - expected:
            per_bucket[name][1] += 1
        for name in expected - actual:
            per_bucket[name][2] += 1
        actual_evidence = {
            evidence["kind"] for decision in classification.provenance["decisions"]
            if decision["decision"] == "matched" for evidence in decision["matched_by"]
        }
        expected_evidence = set(source["expected_evidence_kinds"])
        subtype_ok = result.get("bats_subtype") == source.get("expected_subtype")
        evidence_ok = expected_evidence <= actual_evidence
        personal_ok = result["personal_match"] is source["expected_personal"]
        personal_correct += personal_ok
        bad_forbidden = sorted(actual & forbidden)
        if actual != expected or bad_forbidden or not subtype_ok or not evidence_ok or not personal_ok:
            violations.append({
                "lot_number": source["lot_number"], "expected": sorted(expected),
                "actual": sorted(actual), "forbidden_matched": bad_forbidden,
                "expected_subtype": source.get("expected_subtype"),
                "actual_subtype": result.get("bats_subtype"),
                "missing_evidence": sorted(expected_evidence - actual_evidence),
                "expected_personal": source["expected_personal"],
                "actual_personal": result["personal_match"],
                "rationale": source["rationale"],
            })
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    bucket_metrics = {}
    for name, (b_tp, b_fp, b_fn) in sorted(per_bucket.items()):
        bucket_metrics[name] = {
            "true_positive": b_tp, "false_positive": b_fp, "false_negative": b_fn,
            "precision": b_tp / (b_tp + b_fp) if b_tp + b_fp else 1.0,
            "recall": b_tp / (b_tp + b_fn) if b_tp + b_fn else 1.0,
            "positive_examples": b_tp + b_fn,
        }
    return {
        "rows": len(rows), "true_positive_pairs": tp, "false_positive_pairs": fp,
        "false_negative_pairs": fn, "micro_precision": precision, "micro_recall": recall,
        "personal_accuracy": personal_correct / len(rows), "per_bucket": bucket_metrics,
        "violations": violations,
    }


def passes_gates(report: dict[str, Any], coverage_failures: list[str]) -> tuple[bool, list[str]]:
    failures = list(coverage_failures)
    if report["micro_precision"] < 0.98:
        failures.append(f"micro precision {report['micro_precision']:.1%} < 98%")
    if report["micro_recall"] < 0.95:
        failures.append(f"micro recall {report['micro_recall']:.1%} < 95%")
    if report["personal_accuracy"] < 1.0:
        failures.append(f"personal hard-gate accuracy {report['personal_accuracy']:.1%} < 100%")
    for name, metrics in report["per_bucket"].items():
        if metrics["positive_examples"] >= MIN_POSITIVES and metrics["recall"] < 0.90:
            failures.append(f"{name} recall {metrics['recall']:.1%} < 90%")
    if any(row["forbidden_matched"] for row in report["violations"]):
        failures.append("one or more explicit forbidden-bucket assertions failed")
    if any(row["missing_evidence"] for row in report["violations"]):
        failures.append("one or more expected provenance assertions failed")
    if any(row["expected_subtype"] != row["actual_subtype"] for row in report["violations"]):
        failures.append("one or more subtype assertions failed")
    return not failures, failures


def evaluate_gold(path: Path, rules: Rules) -> dict[str, Any]:
    rows, exemptions = load_gold(path)
    coverage = validate_coverage(rows, rules, exemptions)
    report = evaluate(rows, DeterministicClassifier(rules))
    passed, failures = passes_gates(report, coverage)
    report.update({"accuracy_gates_passed": passed, "gate_failures": failures,
                   "coverage_failures": coverage})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--buckets", type=Path, default=Path("buckets.yaml"))
    parser.add_argument("--profile", type=Path, default=Path("profile.yaml"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = evaluate_gold(args.gold, load_rules(args.buckets, args.profile))
    except (ConfigError, GoldError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["accuracy_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
