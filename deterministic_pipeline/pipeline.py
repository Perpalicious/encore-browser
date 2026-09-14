"""End-to-end local processing, reporting, and bundle generation."""

from __future__ import annotations

import json
import os
import hashlib
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.slim import slim_item

from .classifier import DeterministicClassifier
from .config import Rules
from .normalize import strict_fingerprint


class PipelineError(RuntimeError):
    pass


PRODUCTION_BUNDLE = (Path(__file__).resolve().parents[1]
                     / "viewer/src/data/auction_bundle.json").resolve()


def is_production_bundle(path: Path) -> bool:
    if path.resolve() == PRODUCTION_BUNDLE:
        return True
    try:
        return path.exists() and os.path.samefile(path, PRODUCTION_BUNDLE)
    except OSError:
        return False


def load_items(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PipelineError(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"invalid JSON in {path}: {exc}") from exc
    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list) or any(not isinstance(row, dict) for row in items):
        raise PipelineError("input must be an array, or an object with an items array")
    for index, row in enumerate(items):
        lot_number = row.get("lot_number")
        if not isinstance(lot_number, str) or not lot_number.strip():
            raise PipelineError(f"input item {index}.lot_number must be a nonempty string")
        if not isinstance(row.get("title"), str) or not row["title"].strip():
            raise PipelineError(f"input item {index}.title must be a nonempty string")
        if row.get("condition") is not None and not isinstance(row["condition"], str):
            raise PipelineError(f"input item {index}.condition must be a string or null")
        if "hibid_category_path" in row and not isinstance(row["hibid_category_path"], str):
            raise PipelineError(f"input item {index}.hibid_category_path must be a string")
        if "category_path" in row:
            category = row["category_path"]
            if not isinstance(category, list) or any(not isinstance(v, str) for v in category):
                raise PipelineError(f"input item {index}.category_path must be a string list")
        has_breadcrumb = isinstance(row.get("hibid_category_path"), str) and bool(row["hibid_category_path"].strip())
        has_path = isinstance(row.get("category_path"), list) and bool(row["category_path"])
        if not has_breadcrumb and not has_path:
            raise PipelineError(f"input item {index} needs a nonempty category path")
        for field in ("description", "description_raw", "model", "size", "notes",
                      "functional", "missing_parts", "damage", "missing_major_parts"):
            if row.get(field) is not None and not isinstance(row[field], str):
                raise PipelineError(f"input item {index}.{field} must be a string or null")
        for field in ("damaged", "seal_intact"):
            if row.get(field) is not None and not isinstance(row[field], bool):
                raise PipelineError(f"input item {index}.{field} must be boolean or null")
    return items


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _reference_index(path: Path | None) -> dict[str, set[str]]:
    if path is None:
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"cannot read valid reference JSON {path}: {exc}") from exc
    items = raw.get("lots", raw.get("items")) if isinstance(raw, dict) else raw
    if not isinstance(items, list) or any(not isinstance(row, dict) for row in items):
        raise PipelineError("reference must contain a lots/items array")
    result: dict[str, set[str]] = {}
    for index, row in enumerate(items):
        key = str(row.get("lot_number") or "")
        buckets = row.get("bat_buckets", row.get("bats_buckets")) or []
        if not key or not isinstance(buckets, list) or any(not isinstance(v, str) for v in buckets):
            raise PipelineError(f"reference item {index} has invalid lot_number/buckets")
        if key in result:
            raise PipelineError(f"reference has duplicate lot_number: {key}")
        result[key] = set(buckets)
    return result


def classification_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Preserve accepted structured scrape fields while reusing legacy parsing."""
    item = slim_item(raw)
    if isinstance(raw.get("category_path"), list) and raw["category_path"]:
        item["category_path"] = list(raw["category_path"])
        item.pop("category", None)
    for field in ("model", "size", "notes", "functional", "missing_parts",
                  "damage", "damaged", "missing_major_parts", "seal_intact"):
        value = raw.get(field)
        if value not in (None, "", []):
            item[field] = value
    return item


def process(raw_items: list[dict[str, Any]], rules: Rules,
            reference: dict[str, set[str]] | None = None) -> tuple[list[dict], list[dict], dict]:
    if not raw_items:
        raise PipelineError("input contains zero lots")
    keys = [str(row.get("lot_number") or "") for row in raw_items]
    if any(not key for key in keys):
        raise PipelineError("every input lot must have a non-empty lot_number")
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise PipelineError(f"duplicate lot_number values: {duplicates[:5]}")

    slim = [classification_item(row) for row in raw_items]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in slim:
        grouped.setdefault(strict_fingerprint(row), []).append(row)
    for members in grouped.values():
        members.sort(key=lambda row: str(row["lot_number"]))

    classifier = DeterministicClassifier(rules)
    categorized: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    unresolved_counts: Counter[str] = Counter()
    exclusion_counts: Counter[str] = Counter()
    matched_products = 0
    subtype_counts: Counter[str] = Counter()
    personal_tag_counts: Counter[str] = Counter()
    project_counts: Counter[str] = Counter()
    for fingerprint in sorted(grouped):
        members = grouped[fingerprint]
        result = classifier.classify(members[0])
        matched_products += result.row["is_bats_list"]
        for member in members:
            row = dict(result.row)
            row["lot_number"] = str(member["lot_number"])
            categorized.append(row)
            detail = dict(result.provenance)
            detail.update({"lot_number": row["lot_number"],
                           "strict_fingerprint": fingerprint,
                           "representative_lot": str(members[0]["lot_number"])})
            provenance.append(detail)
            bucket_counts.update(row["bats_buckets"])
            if row.get("bats_subtype"):
                subtype_counts.update([row["bats_subtype"]])
            personal_tag_counts.update(row.get("personal_tags") or [])
            project_counts.update(evidence["value"] for evidence in detail["project_evidence"])
            unresolved_counts.update(detail["unresolved"])
            exclusion_counts.update(
                decision["bucket"] for decision in detail["decisions"]
                if decision["decision"] == "excluded")

    categorized.sort(key=lambda row: row["lot_number"])
    provenance.sort(key=lambda row: row["lot_number"])
    if len(categorized) != len(raw_items) or len({r["lot_number"] for r in categorized}) != len(raw_items):
        raise PipelineError("classification did not preserve every input lot exactly once")
    if any(bool(r["bats_buckets"]) != r["is_bats_list"] for r in categorized):
        raise PipelineError("is_bats_list invariant failed")

    reference = reference or {}
    predicted = {row["lot_number"]: set(row["bats_buckets"]) for row in categorized}
    common = predicted.keys() & reference.keys()
    tp = sum(len(predicted[k] & reference[k]) for k in common)
    fp = sum(len(predicted[k] - reference[k]) for k in common)
    fn = sum(len(reference[k] - predicted[k]) for k in common)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    per_bucket_raw: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    difference_samples: list[dict[str, Any]] = []
    for key in sorted(common):
        new, old = predicted[key], reference[key]
        for name in new & old:
            per_bucket_raw[name][0] += 1
        for name in new - old:
            per_bucket_raw[name][1] += 1
        for name in old - new:
            per_bucket_raw[name][2] += 1
        if new != old and len(difference_samples) < 100:
            difference_samples.append({"lot_number": key,
                                       "deterministic": sorted(new),
                                       "legacy": sorted(old)})
    per_bucket = {
        name: {"shared": values[0], "new_only": values[1],
               "reference_only": values[2],
               "precision_agreement": values[0] / (values[0] + values[1])
               if values[0] + values[1] else None,
               "recall_agreement": values[0] / (values[0] + values[2])
               if values[0] + values[2] else None}
        for name, values in sorted(per_bucket_raw.items())
    }
    package_dir = Path(__file__).resolve().parent
    code_material = b"".join(
        path.read_bytes() for path in sorted(package_dir.glob("*.py"))
    )
    code_hash = hashlib.sha256(code_material).hexdigest()[:20]
    category_counts = Counter(
        str(row.get("category") or "Uncategorized") for row in slim)
    zero_match_rules = sorted(rule.name for rule in rules.buckets
                              if not bucket_counts[rule.name])
    report = {
        "schema_version": 1,
        "ruleset": rules.ruleset,
        "input_lots": len(raw_items),
        "valid_lots": len(categorized),
        "rejected_records": 0,
        "distinct_products": len(grouped),
        "exact_duplicates": len(raw_items) - len(grouped),
        "bat_lots": sum(row["is_bats_list"] for row in categorized),
        "personal_lots": sum(row["personal_match"] for row in categorized),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "subtype_counts": dict(sorted(subtype_counts.items())),
        "personal_tag_counts": dict(sorted(personal_tag_counts.items())),
        "project_context_counts": dict(sorted(project_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "rules_matching_zero_lots": zero_match_rules,
        "unmatched_products": len(grouped) - matched_products,
        "unresolved_counts": dict(sorted(unresolved_counts.items())),
        "classifier_code_hash": code_hash,
        "design_guarantee": "classifier package contains no model or network client",
        "reference_comparison": {
            "source": "legacy labels; not human ground truth" if reference else None,
            "joined_lots": len(common), "true_positive_pairs": tp,
            "new_only_pairs": fp, "reference_only_pairs": fn,
            "pair_agreement_precision": precision,
            "pair_agreement_recall": recall,
            "per_bucket": per_bucket,
            "difference_samples": difference_samples,
        },
    }
    return categorized, provenance, report


def markdown_report(report: dict[str, Any]) -> str:
    comparison = report["reference_comparison"]
    lines = [
        "# Deterministic classification report", "",
        f"- Ruleset: `{report['ruleset']}`",
        f"- Classifier code: `{report['classifier_code_hash']}`",
        f"- Input and valid lots: {report['input_lots']:,} / {report['valid_lots']:,}",
        f"- Distinct products: {report['distinct_products']:,}",
        f"- Exact duplicates fanned out: {report['exact_duplicates']:,}",
        f"- Bat bucket lots: {report['bat_lots']:,}",
        f"- Personal picks with explicit evidence: {report['personal_lots']:,}",
        "- Runtime and memory are recorded separately in the performance report.",
        "- Design guarantee: classifier package contains no model or network client.", "",
        "## Unresolved evidence", "",
    ]
    if report["unresolved_counts"]:
        lines.extend(f"- {name}: {count:,}" for name, count in report["unresolved_counts"].items())
    else:
        lines.append("- None")
    lines.extend(["", "## Bucket volume", ""])
    lines.extend(f"- {name}: {count:,}" for name, count in report["bucket_counts"].items())
    if report["rules_matching_zero_lots"]:
        lines.extend(["", "## Rules matching zero lots", ""])
        lines.extend(f"- {name}" for name in report["rules_matching_zero_lots"])
    if comparison["joined_lots"]:
        p = comparison["pair_agreement_precision"]
        r = comparison["pair_agreement_recall"]
        lines.extend(["", "## Legacy-label comparison", "",
                      "These are agreement measurements against prior generated labels, not accuracy measurements.", "",
                      f"- Joined lots: {comparison['joined_lots']:,}",
                      f"- Pair precision agreement: {p:.1%}" if p is not None else "- Pair precision agreement: n/a",
                      f"- Pair recall agreement: {r:.1%}" if r is not None else "- Pair recall agreement: n/a"])
    return "\n".join(lines) + "\n"


def run(*, raw_path: Path, categorized_path: Path, provenance_path: Path,
        report_path: Path, markdown_path: Path, performance_path: Path, rules: Rules,
        bundle_path: Path | None, buckets_path: Path,
        reference_path: Path | None = None) -> dict[str, Any]:
    import resource

    if bundle_path is not None:
        if is_production_bundle(bundle_path):
            raise PipelineError("production bundle publication is unavailable during shadow evaluation")
        if bundle_path.exists() and bundle_path.is_dir():
            raise PipelineError(f"bundle output is a directory: {bundle_path}")
        ancestor = bundle_path.parent
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
            raise PipelineError(f"bundle output parent is not writable: {bundle_path.parent}")
    started = time.perf_counter()
    raw_items = load_items(raw_path)
    categorized, provenance, report = process(raw_items, rules, _reference_index(reference_path))
    performance = {
        "measurement_only": True,
        "input_lots": len(raw_items),
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    categorized_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".deterministic-run-",
                                     dir=categorized_path.parent) as stage_name:
        stage = Path(stage_name)
        staged_categorized = stage / "categorized.json"
        staged_provenance = stage / "provenance.json"
        staged_report = stage / "report.json"
        staged_markdown = stage / "report.md"
        staged_performance = stage / "performance.json"
        _atomic_json(staged_categorized, categorized)
        _atomic_json(staged_provenance, provenance)
        _atomic_json(staged_report, report)
        _atomic_json(staged_performance, performance)
        staged_markdown.write_text(markdown_report(report), encoding="utf-8")
        staged_bundle = stage / "bundle.json"
        if bundle_path is not None:
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, "-m", "build", "--raw", str(raw_path),
                       "--categorized", str(staged_categorized),
                       "--output", str(staged_bundle), "--buckets", str(buckets_path)]
            completed = subprocess.run(command, text=True, capture_output=True)
            if completed.returncode:
                raise PipelineError(f"bundle build failed:\n{completed.stdout}{completed.stderr}")
        for source, destination in (
            (staged_categorized, categorized_path),
            (staged_provenance, provenance_path),
            (staged_report, report_path),
            (staged_markdown, markdown_path),
            (staged_performance, performance_path),
        ):
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
        if bundle_path is not None:
            os.replace(staged_bundle, bundle_path)
    return report
