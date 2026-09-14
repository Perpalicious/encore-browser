"""Create and review a human gold set without model or network calls."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
import webbrowser
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .classifier import DeterministicClassifier
from .config import ConfigError, Rules, load_rules
from .evaluate import (EVIDENCE_KINDS, MIN_NEGATIVES, MIN_POSITIVES,
                       REQUIRED_CRITICAL, evaluate,
                       passes_gates, validate_coverage)
from .normalize import normalize_text, strict_fingerprint
from .pipeline import (PRODUCTION_BUNDLE, PipelineError, classification_item,
                       load_items)

SCHEMA_VERSION = 2
ATTESTATION_STATEMENT = "I affirm that I personally reviewed every exported record against its source listing."
EDITABLE = {
    "expected_buckets", "forbidden_buckets", "expected_subtype",
    "expected_evidence_kinds", "expected_personal", "critical_assertions",
    "rationale", "reviewed",
}
FEEDBACK_DISPOSITIONS = {
    "correct", "rule_miss", "overmatch", "taxonomy_issue",
    "source_insufficient", "revisit",
}
FEEDBACK_REASONS = {
    "seed_missing", "exclusion_missing", "category_mismatch",
    "subtype_mismatch", "personal_gate", "multi_label", "ambiguous_source",
    "other",
}
FEEDBACK_EDITABLE = {
    "disposition", "reason", "notes", "suggested_buckets", "suggested_seed",
    "suggested_exclusion", "suggested_subtype",
}
SOURCE_FIELDS = (
    "lot_number", "title", "condition", "category", "category_path",
    "hibid_category_path", "description", "description_raw", "model", "size",
    "notes", "functional", "missing_parts", "missing_major_parts", "damage",
    "damaged", "seal_intact", "image_url", "thumb_url", "additional_images",
    "lot_url", "close_at",
)
REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = Path(__file__).with_name("review_dashboard")
DASHBOARD_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/assets/visibility.css": ("visibility.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
MALFORMED_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


class ReviewError(ValueError):
    """Review input or state is invalid."""


class ConflictError(ReviewError):
    """A stale browser attempted to replace newer review work."""


def decode_item_id(segment: str) -> str:
    """Decode one URL path segment without accepting ambiguous encodings."""
    if not segment or len(segment) > 512 or MALFORMED_PERCENT.search(segment):
        raise ReviewError("malformed review item id")
    try:
        value = unquote(segment, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ReviewError("malformed review item id") from exc
    if not value or "/" in value or "\x00" in value:
        raise ReviewError("malformed review item id")
    return value


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: object, *, backup: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if backup and path.is_file():
            backup_path = path.with_name(path.name + ".bak")
            backup_fd, backup_temp = tempfile.mkstemp(prefix=f".{backup_path.name}.", dir=path.parent)
            try:
                with os.fdopen(backup_fd, "wb") as handle:
                    handle.write(path.read_bytes()); handle.flush(); os.fsync(handle.fileno())
                os.replace(backup_temp, backup_path)
            finally:
                if os.path.exists(backup_temp):
                    os.unlink(backup_temp)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"cannot read valid {label} JSON {path}: {exc}") from exc


def _legacy(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    document = _read_json(path, "legacy reference")
    rows = document.get("lots", document.get("items")) if isinstance(document, dict) else document
    if not isinstance(rows, list):
        raise ReviewError("legacy reference needs a lots/items array")
    result = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not str(row.get("lot_number") or ""):
            raise ReviewError(f"legacy reference row {index} needs lot_number")
        key = str(row["lot_number"])
        buckets = row.get("bats_buckets", row.get("bat_buckets", [])) or []
        if not isinstance(buckets, list) or any(not isinstance(v, str) for v in buckets):
            raise ReviewError(f"legacy reference row {index} has invalid buckets")
        result[key] = {"buckets": sorted(set(buckets)),
                       "subtype": row.get("bats_subtype"),
                       "personal": bool(row.get("personal_match"))}
    return result


def _source(row: dict[str, Any]) -> dict[str, Any]:
    result = {field: row[field] for field in SOURCE_FIELDS if field in row}
    result["lot_number"] = str(row["lot_number"])
    return result


def _selection_keys(classification: Any, legacy: dict[str, Any] | None) -> set[str]:
    row, provenance = classification.row, classification.provenance
    result = {f"positive:{bucket}" for bucket in row["bats_buckets"]}
    result.update(
        f"near_negative:{decision['bucket']}" for decision in provenance["decisions"]
        if decision["decision"] in {"excluded", "unresolved"}
    )
    if len(row["bats_buckets"]) > 1:
        result.add("multi_label")
    if provenance["unresolved"]:
        result.add("ambiguous")
    if provenance["personal_hard_gates"]:
        result.add("personal_hard_gate")
    if legacy is not None and set(legacy["buckets"]) != set(row["bats_buckets"]):
        result.add("legacy_disagreement")
    if "Keyboards & PC peripherals" in row["bats_buckets"]:
        result.add("critical:keyboard")
    if any(item["kind"] == "proven_resale" for item in provenance["personal_evidence"]):
        result.add("critical:proven_resale")
    if provenance["personal_hard_gates"]:
        result.add("critical:personal_hard_gate")
    return result


def generate_session(raw_path: Path, output: Path, rules: Rules, reviewer: str,
                     legacy_path: Path | None = None, per_stratum: int = 2,
                     protected_paths: list[Path] | None = None) -> dict[str, Any]:
    protected = [raw_path, PRODUCTION_BUNDLE, REPO_ROOT / "buckets.yaml",
                 REPO_ROOT / "profile.yaml", *(protected_paths or [])]
    if legacy_path is not None:
        protected.append(legacy_path)
    validate_generation_path(output, protected)
    if not reviewer.strip():
        raise ReviewError("reviewer must be a nonempty name")
    if per_stratum < 1:
        raise ReviewError("per-stratum must be at least 1")
    raw = load_items(raw_path)
    legacy = _legacy(legacy_path)
    classifier = DeterministicClassifier(rules)
    products: dict[str, dict[str, Any]] = {}
    for source in raw:
        slim = classification_item(source)
        fingerprint = strict_fingerprint(slim)
        current = products.get(fingerprint)
        if current is None or str(slim["lot_number"]) < str(current["slim"]["lot_number"]):
            products[fingerprint] = {"slim": slim, "raw": source}

    candidates: list[dict[str, Any]] = []
    for fingerprint, product in sorted(products.items()):
        result = classifier.classify(product["slim"])
        old = legacy.get(str(product["slim"]["lot_number"]))
        keys = sorted(_selection_keys(result, old))
        candidates.append({
            "id": fingerprint, "source": _source(product["raw"]),
            "selection_keys": keys,
            "prediction": {
                "warning": "Machine context only; never a human label.",
                "classifier": result.row, "provenance": result.provenance,
                "legacy": old,
            },
        })

    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        for key in candidate["selection_keys"]:
            by_key[key].append(candidate)
    wanted = [f"positive:{rule.name}" for rule in rules.buckets]
    wanted += [f"near_negative:{rule.name}" for rule in rules.buckets]
    wanted += ["legacy_disagreement", "ambiguous", "multi_label", "personal_hard_gate",
               "critical:keyboard", "critical:proven_resale", "critical:personal_hard_gate"]
    chosen: dict[str, dict[str, Any]] = {}
    coverage: dict[str, dict[str, int]] = {}
    for key in wanted:
        pool = sorted(by_key.get(key, []), key=lambda item: item["id"])
        coverage[key] = {"available": len(pool), "selected": min(len(pool), per_stratum)}
        for candidate in pool[:per_stratum]:
            chosen[candidate["id"]] = candidate

    items = []
    for candidate in sorted(chosen.values(), key=lambda item: item["id"]):
        source = _source(candidate["source"])
        # The evaluator calls the classifier directly, while production first
        # converts the raw HiBid breadcrumb to the slim `category` field.
        # Persist that exact classifier input alongside the original breadcrumb.
        slim = products[candidate["id"]]["slim"]
        if "category" in slim:
            source["category"] = slim["category"]
        if "category_path" in slim:
            source["category_path"] = slim["category_path"]
        items.append({
            **candidate,
            "source": source,
            "review": {
                "reviewed": False, "expected_buckets": None,
                "forbidden_buckets": None, "expected_subtype": None,
                "expected_evidence_kinds": None, "expected_personal": None,
                "critical_assertions": None, "rationale": "",
            },
            "audit": [],
            "revision": 0,
            "feedback": {
                "disposition": None, "reason": None, "notes": "",
                "suggested_buckets": [], "suggested_seed": "",
                "suggested_exclusion": "", "suggested_subtype": "",
            },
            "feedback_audit": [],
            "feedback_revision": 0,
        })
    if not items:
        raise ReviewError("candidate generation found zero reviewable products")
    session = {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "csrf_token": secrets.token_urlsafe(32),
        "created_at": now(), "updated_at": now(), "reviewer": reviewer.strip(),
        "source": {"raw_path": str(raw_path.resolve()),
                   "legacy_path": str(legacy_path.resolve()) if legacy_path else None,
                   "ruleset": rules.ruleset, "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest()},
        "sampling": {"method": "strict-product deterministic stratified v1",
                     "per_stratum": per_stratum, "products_seen": len(products),
                     "candidates_selected": len(items), "coverage": coverage},
        "rare_bucket_exemptions": {}, "items": items,
        "attestation": None, "exemption_audit": [],
    }
    atomic_json(output, session)
    return session


def _audit_valid(entries: Any) -> bool:
    if not isinstance(entries, list):
        return False
    return all(isinstance(entry, dict) and isinstance(entry.get("at"), str)
               and isinstance(entry.get("actor"), str) and bool(entry["actor"].strip())
               and isinstance(entry.get("changes"), dict) for entry in entries)


def load_session(path: Path, rules: Rules | None = None) -> dict[str, Any]:
    try:
        document = _read_json(path, "review session")
    except ReviewError as primary:
        backup = path.with_name(path.name + ".bak")
        if not backup.is_file():
            raise primary
        document = _read_json(backup, "review session backup")
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise ReviewError("unsupported review session schema")
    if not isinstance(document.get("revision"), int) or document["revision"] < 0:
        raise ReviewError("review session revision is invalid")
    if not isinstance(document.get("csrf_token"), str) or len(document["csrf_token"]) < 32:
        raise ReviewError("review session CSRF token is invalid")
    if not isinstance(document.get("source"), dict) or not isinstance(document["source"].get("ruleset"), str):
        raise ReviewError("review session source metadata is invalid")
    exemption_audit = document.get("exemption_audit")
    if not isinstance(exemption_audit, list) or any(
            not isinstance(entry, dict) or not isinstance(entry.get("at"), str)
            or not isinstance(entry.get("actor"), str) or not entry["actor"].strip()
            or "before" not in entry or "after" not in entry
            for entry in exemption_audit):
        raise ReviewError("review session exemption audit is invalid")
    if rules is not None and document["source"]["ruleset"] != rules.ruleset:
        raise ReviewError("rules/config drift detected; regenerate the review session explicitly")
    items = document.get("items")
    if not isinstance(items, list) or not items:
        raise ReviewError("review session items must be a nonempty list")
    identifiers: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in identifiers:
            raise ReviewError(f"review session item {index} has an invalid or duplicate id")
        identifiers.add(item["id"])
        if not isinstance(item.get("source"), dict) or not isinstance(item["source"].get("lot_number"), str):
            raise ReviewError(f"review session item {index} source is invalid")
        if not isinstance(item.get("revision"), int) or item["revision"] < 0:
            raise ReviewError(f"review session item {index} revision is invalid")
        if not _audit_valid(item.get("audit")):
            raise ReviewError(f"review session item {index} audit is invalid")
        # Sessions generated by the first review UI remain resumable. Feedback
        # is an independent annotation layer and defaults to an empty record.
        item.setdefault("feedback", {
            "disposition": None, "reason": None, "notes": "",
            "suggested_buckets": [], "suggested_seed": "",
            "suggested_exclusion": "", "suggested_subtype": "",
        })
        item.setdefault("feedback_audit", [])
        item.setdefault("feedback_revision", 0)
        if not isinstance(item["feedback_revision"], int) or item["feedback_revision"] < 0:
            raise ReviewError(f"review session item {index} feedback revision is invalid")
        if not _audit_valid(item["feedback_audit"]):
            raise ReviewError(f"review session item {index} feedback audit is invalid")
        if rules is not None:
            validate_review(item.get("review"), rules, item.get("source"), item.get("prediction"))
            validate_feedback(item.get("feedback"), rules)
        if isinstance(item.get("review"), dict) and item["review"].get("reviewed") and not item["audit"]:
            raise ReviewError(f"reviewed session item {index} lacks audit history")
    return document


def validate_exemptions(value: Any, rules: Rules) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewError("rare_bucket_exemptions must be an object")
    known = {rule.name for rule in rules.buckets}
    if set(value) - known:
        raise ReviewError("rare_bucket_exemptions references an unknown bucket")
    for bucket, exemption in value.items():
        if not isinstance(exemption, dict) or set(exemption) != {
                "reason", "min_positive", "min_negative"}:
            raise ReviewError(f"{bucket} exemption needs reason, min_positive, and min_negative")
        if not isinstance(exemption["reason"], str) or len(exemption["reason"].strip()) < 20:
            raise ReviewError(f"{bucket} exemption reason must be at least 20 characters")
        for field in ("min_positive", "min_negative"):
            if type(exemption[field]) is not int or not 1 <= exemption[field] < 20:
                raise ReviewError(f"{bucket} exemption {field} must be 1..19")
    return value


def validate_feedback(value: Any, rules: Rules) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FEEDBACK_EDITABLE:
        raise ReviewError(f"feedback must contain exactly {sorted(FEEDBACK_EDITABLE)}")
    disposition = value["disposition"]
    if disposition is not None and disposition not in FEEDBACK_DISPOSITIONS:
        raise ReviewError("feedback disposition is not controlled")
    reason = value["reason"]
    if reason is not None and reason not in FEEDBACK_REASONS:
        raise ReviewError("feedback reason is not controlled")
    if disposition is None and reason is not None:
        raise ReviewError("feedback reason requires a disposition")
    if disposition is None and (value["notes"] or value["suggested_buckets"]
                                or value["suggested_seed"] or value["suggested_exclusion"]
                                or value["suggested_subtype"]):
        raise ReviewError("feedback details require a disposition")
    if disposition not in {None, "correct"} and reason is None:
        raise ReviewError("non-correct feedback requires a controlled reason")
    buckets = value["suggested_buckets"]
    known = {rule.name for rule in rules.buckets}
    if (not isinstance(buckets, list) or any(not isinstance(v, str) or not v for v in buckets)
            or len(buckets) != len(set(buckets)) or set(buckets) - known):
        raise ReviewError("feedback suggested_buckets must be unique controlled buckets")
    for field in ("notes", "suggested_seed", "suggested_exclusion", "suggested_subtype"):
        if not isinstance(value[field], str):
            raise ReviewError(f"feedback {field} must be a string")
        if len(value[field]) > 5000:
            raise ReviewError(f"feedback {field} is too long")
    known_subtypes = {subtype for rule in rules.buckets for subtype in rule.subtypes}
    if value["suggested_subtype"] and value["suggested_subtype"] not in known_subtypes:
        raise ReviewError("feedback suggested_subtype is not controlled")
    return value


def validate_review(review: Any, rules: Rules, source: dict[str, Any] | None = None,
                    prediction: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(review, dict) or set(review) != EDITABLE:
        raise ReviewError(f"review must contain exactly {sorted(EDITABLE)}")
    if not isinstance(review["reviewed"], bool):
        raise ReviewError("reviewed must be boolean")
    known = {rule.name for rule in rules.buckets}
    for field in ("expected_buckets", "forbidden_buckets", "expected_evidence_kinds",
                  "critical_assertions"):
        value = review[field]
        if value is not None and (not isinstance(value, list) or
                                  any(not isinstance(v, str) or not v for v in value)):
            raise ReviewError(f"{field} must be null or a string list")
        if isinstance(value, list) and len(value) != len(set(value)):
            raise ReviewError(f"{field} contains duplicate values")
    expected = set(review["expected_buckets"] or [])
    forbidden = set(review["forbidden_buckets"] or [])
    if (expected | forbidden) - known:
        raise ReviewError("review references an unknown bucket")
    if expected & forbidden:
        raise ReviewError("a bucket cannot be both expected and forbidden")
    evidence = set(review["expected_evidence_kinds"] or [])
    if evidence - EVIDENCE_KINDS:
        raise ReviewError(f"unknown evidence kinds: {sorted(evidence - EVIDENCE_KINDS)}")
    assertions = set(review["critical_assertions"] or [])
    if assertions - REQUIRED_CRITICAL:
        raise ReviewError(f"unknown critical assertions: {sorted(assertions - REQUIRED_CRITICAL)}")
    subtype = review["expected_subtype"]
    if subtype is not None and not isinstance(subtype, str):
        raise ReviewError("expected_subtype must be null or string")
    if subtype is not None:
        allowed = {subtype_value for rule in rules.buckets if rule.name in expected
                   for subtype_value in rule.subtypes}
        if subtype not in allowed:
            raise ReviewError("expected_subtype is not controlled by an expected bucket")
    if review["expected_personal"] is not None and not isinstance(review["expected_personal"], bool):
        raise ReviewError("expected_personal must be null or boolean")
    if not isinstance(review["rationale"], str):
        raise ReviewError("rationale must be a string")
    if review["reviewed"]:
        missing = [key for key in ("expected_buckets", "forbidden_buckets",
                                    "expected_evidence_kinds", "expected_personal",
                                    "critical_assertions") if review[key] is None]
        if missing or len(review["rationale"].strip()) < 10:
            raise ReviewError(f"reviewed item is incomplete: {missing or ['rationale']}")
        if source is None or prediction is None:
            raise ReviewError("reviewed item needs immutable source and candidate context")
        source_text = normalize_text(" ".join(str(source.get(field) or "") for field in
                                               ("title", "category", "hibid_category_path")))
        if "keyboard" in assertions and (
                "Keyboards & PC peripherals" not in expected or "keyboard" not in source_text):
            raise ReviewError("keyboard assertion lacks keyboard source semantics and expected bucket")
        provenance = prediction.get("provenance", {}) if isinstance(prediction, dict) else {}
        if "proven_resale" in assertions:
            has_signal = any(entry.get("kind") == "proven_resale"
                             for entry in provenance.get("personal_evidence", []))
            if review["expected_personal"] is not True or not has_signal:
                raise ReviewError("proven_resale assertion lacks reviewed personal result/source signal")
        if "personal_hard_gate" in assertions:
            gates = provenance.get("personal_hard_gates", [])
            if review["expected_personal"] is not False or not gates:
                raise ReviewError("personal_hard_gate assertion lacks a typed source gate")
    return review


class SessionStore:
    def __init__(self, path: Path, rules: Rules):
        self.path, self.rules, self.lock = path, rules, threading.Lock()

    def read(self) -> dict[str, Any]:
        with self.lock:
            return load_session(self.path, self.rules)

    def update(self, item_id: str, review: Any, actor: str,
               expected_revision: int) -> dict[str, Any]:
        if not actor.strip():
            raise ReviewError("actor is required")
        with self.lock:
            session = load_session(self.path, self.rules)
            item = next((row for row in session["items"] if row.get("id") == item_id), None)
            if item is None:
                raise ReviewError("unknown review item")
            if not isinstance(expected_revision, int) or expected_revision != item["revision"]:
                raise ConflictError("stale item revision; reload before saving")
            validated = validate_review(review, self.rules, item["source"], item["prediction"])
            before = item["review"]
            changes = {key: {"before": before.get(key), "after": validated.get(key)}
                       for key in EDITABLE if before.get(key) != validated.get(key)}
            if changes:
                item["review"] = validated
                item["audit"].append({"at": now(), "actor": actor.strip(), "changes": changes})
                item["revision"] += 1
                session["revision"] += 1
                session["updated_at"] = now()
                atomic_json(self.path, session, backup=True)
            return item

    def update_exemptions(self, exemptions: Any, actor: str,
                          expected_revision: int) -> dict[str, Any]:
        if not actor.strip():
            raise ReviewError("actor is required")
        validated = validate_exemptions(exemptions, self.rules)
        with self.lock:
            session = load_session(self.path, self.rules)
            if not isinstance(expected_revision, int) or expected_revision != session["revision"]:
                raise ConflictError("stale session revision; reload before saving exemptions")
            before = session.get("rare_bucket_exemptions", {})
            if before != validated:
                session["rare_bucket_exemptions"] = validated
                session.setdefault("exemption_audit", []).append(
                    {"at": now(), "actor": actor.strip(), "before": before, "after": validated})
                session["revision"] += 1
                session["updated_at"] = now()
                atomic_json(self.path, session, backup=True)
            return validated

    def update_feedback(self, item_id: str, feedback: Any, actor: str,
                        expected_revision: int) -> dict[str, Any]:
        if not actor.strip():
            raise ReviewError("actor is required")
        validated = validate_feedback(feedback, self.rules)
        with self.lock:
            session = load_session(self.path, self.rules)
            item = next((row for row in session["items"] if row.get("id") == item_id), None)
            if item is None:
                raise ReviewError("unknown review item")
            if not isinstance(expected_revision, int) or expected_revision != item["feedback_revision"]:
                raise ConflictError("stale feedback revision; reload before saving")
            before = item["feedback"]
            changes = {key: {"before": before.get(key), "after": validated.get(key)}
                       for key in FEEDBACK_EDITABLE if before.get(key) != validated.get(key)}
            if changes:
                item["feedback"] = validated
                item["feedback_audit"].append({"at": now(), "actor": actor.strip(),
                                                "changes": changes})
                item["feedback_revision"] += 1
                session["revision"] += 1
                session["updated_at"] = now()
                atomic_json(self.path, session, backup=True)
            return item


def progress(session: dict[str, Any], rules: Rules | None = None) -> dict[str, Any]:
    reviewed = [item for item in session["items"] if item["review"]["reviewed"]]
    positive, negative = Counter(), Counter()
    for item in reviewed:
        positive.update(item["review"]["expected_buckets"] or [])
        negative.update(item["review"]["forbidden_buckets"] or [])
    bucket_names = ([rule.name for rule in rules.buckets] if rules is not None
                    else sorted(set(positive) | set(negative)))
    exemptions = session.get("rare_bucket_exemptions", {})
    by_bucket = {}
    blockers = []
    for name in bucket_names:
        exemption = exemptions.get(name, {})
        target_positive = exemption.get("min_positive", MIN_POSITIVES)
        target_negative = exemption.get("min_negative", MIN_NEGATIVES)
        subtype = sum(1 for item in reviewed if name in (item["review"]["expected_buckets"] or [])
                      and item["review"]["expected_subtype"] is not None)
        row = {"positive": positive[name], "negative": negative[name], "subtype": subtype,
               "target_positive": target_positive, "target_negative": target_negative,
               "positive_gap": max(0, target_positive - positive[name]),
               "negative_gap": max(0, target_negative - negative[name]),
               "subtype_gap": subtype < 1}
        by_bucket[name] = row
        if row["positive_gap"] or row["negative_gap"] or row["subtype_gap"]:
            blockers.append(name)
    critical = Counter(assertion for item in reviewed
                       for assertion in (item["review"]["critical_assertions"] or []))
    critical_gaps = sorted(REQUIRED_CRITICAL - set(critical))
    feedback = Counter(item["feedback"]["disposition"] or "none" for item in session["items"])
    return {"total": len(session["items"]), "reviewed": len(reviewed),
            "remaining": len(session["items"]) - len(reviewed),
            "completion_percent": round(100 * len(reviewed) / len(session["items"]), 1),
            "by_bucket": by_bucket, "critical": dict(critical),
            "critical_gaps": critical_gaps, "blocking_buckets": blockers,
            "export_blocked": len(reviewed) != len(session["items"]) or bool(blockers) or bool(critical_gaps),
            "feedback_counts": dict(feedback)}


def feedback_export(session: dict[str, Any]) -> dict[str, Any]:
    """Return feedback only; gold truth and hidden predictions stay separate."""
    rows = []
    for item in session["items"]:
        if item["feedback"]["disposition"] is None:
            continue
        source = item["source"]
        rows.append({
            "id": item["id"], "lot_number": source["lot_number"],
            "title": source.get("title"), "category": source.get("category"),
            "feedback": item["feedback"], "feedback_revision": item["feedback_revision"],
            "feedback_audit": item["feedback_audit"],
        })
    return {"schema_version": 1, "exported_at": now(),
            "source_ruleset": session["source"]["ruleset"],
            "notice": "Human feedback only. This file is not gold truth and changes no classifier rules.",
            "items": rows}


def _same_path(left: Path, right: Path) -> bool:
    if left.resolve(strict=False) == right.resolve(strict=False):
        return True
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def validate_export_path(output: Path, protected: list[Path], *,
                         allow_test_fixture: bool = False) -> None:
    if output.is_symlink():
        raise ReviewError("export target cannot be a symlink")
    if output.exists() and output.is_dir():
        raise ReviewError("export target cannot be a directory")
    if output.exists() and output.stat().st_nlink > 1:
        raise ReviewError("export target cannot be a hard-linked file")
    resolved = output.resolve(strict=False)
    for path in protected:
        if _same_path(output, path):
            raise ReviewError(f"export target aliases protected input: {path}")
    try:
        relative = resolved.relative_to(REPO_ROOT)
    except ValueError:
        return
    review_root = (REPO_ROOT / "data/review").resolve(strict=False)
    fixture_root = (REPO_ROOT / "tests/fixtures").resolve(strict=False)
    if resolved == review_root or resolved == fixture_root:
        raise ReviewError("export target must be a file")
    if resolved.is_relative_to(review_root):
        return
    if allow_test_fixture and resolved.is_relative_to(fixture_root):
        return
    raise ReviewError(
        f"protected repository path {relative}; export under data/review/"
        " (or explicitly allow a reviewed test fixture)")


def validate_generation_path(output: Path, protected: list[Path]) -> None:
    """Protect source/config files before a new session can read or write."""
    if output.is_symlink():
        raise ReviewError("review session target cannot be a symlink")
    if output.exists():
        if output.is_dir():
            raise ReviewError("review session target cannot be a directory")
        if output.stat().st_nlink > 1:
            raise ReviewError("review session target cannot be a hard-linked file")
        raise ReviewError("review session target already exists; resume it or choose a new path")
    resolved = output.resolve(strict=False)
    for path in protected:
        if _same_path(output, path):
            raise ReviewError(f"review session target aliases protected input: {path}")
    try:
        relative = resolved.relative_to(REPO_ROOT)
    except ValueError:
        return
    review_root = (REPO_ROOT / "data/review").resolve(strict=False)
    if resolved == review_root:
        raise ReviewError("review session target must be a file")
    if not resolved.is_relative_to(review_root):
        raise ReviewError(f"protected repository path {relative}; write sessions under data/review/")


def export_gold(session_path: Path, output: Path, rules: Rules,
                reviewer: str, reviewed_on: str, attest_human_review: bool,
                *, protected_paths: list[Path] | None = None,
                allow_test_fixture: bool = False) -> dict[str, Any]:
    protected = [session_path, session_path.with_name(session_path.name + ".bak"),
                 PRODUCTION_BUNDLE, REPO_ROOT / "buckets.yaml",
                 REPO_ROOT / "profile.yaml", *(protected_paths or [])]
    protected.extend(session_path.parent.glob(f".{session_path.name}.*"))
    validate_export_path(output, protected, allow_test_fixture=allow_test_fixture)
    session = load_session(session_path, rules)
    for key in ("raw_path", "legacy_path"):
        value = session["source"].get(key)
        if value:
            protected.append(Path(value))
    validate_export_path(output, protected, allow_test_fixture=allow_test_fixture)
    if reviewer.strip() != session["reviewer"]:
        raise ReviewError("reviewer must match the session reviewer")
    if not attest_human_review:
        raise ReviewError(f"human review attestation required: {ATTESTATION_STATEMENT}")
    try:
        attested_date = date.fromisoformat(reviewed_on)
    except (TypeError, ValueError) as exc:
        raise ReviewError("reviewed-on must be an ISO date (YYYY-MM-DD)") from exc
    if attested_date > datetime.now(timezone.utc).date():
        raise ReviewError("reviewed-on cannot be in the future")
    try:
        created_date = datetime.fromisoformat(session["created_at"]).date()
    except (KeyError, TypeError, ValueError) as exc:
        raise ReviewError("review session creation date is invalid") from exc
    if attested_date < created_date:
        raise ReviewError("reviewed-on cannot predate the review session")
    incomplete = [item["source"]["lot_number"] for item in session["items"]
                  if not item["review"]["reviewed"]]
    if incomplete:
        raise ReviewError(f"cannot export: {len(incomplete)} items remain unreviewed")
    rows = []
    for item in session["items"]:
        if not item["audit"]:
            raise ReviewError(f"reviewed item {item['source']['lot_number']} lacks audit history")
        review = validate_review(item["review"], rules, item["source"], item["prediction"])
        source = item["source"]
        row = {key: source[key] for key in SOURCE_FIELDS if key in source}
        row.update({key: review[key] for key in EDITABLE if key != "reviewed"})
        rows.append(row)
    exemptions = validate_exemptions(session.get("rare_bucket_exemptions", {}), rules)
    coverage = validate_coverage(rows, rules, exemptions)
    if coverage:
        raise ReviewError("coverage validation failed; export was not written:\n- " + "\n- ".join(coverage))
    metrics = evaluate(rows, DeterministicClassifier(rules))
    passed, gate_failures = passes_gates(metrics, [])
    report = {**metrics, "accuracy_gates_passed": passed,
              "gate_failures": gate_failures, "coverage_failures": []}
    export = {
        "items": rows,
        "rare_bucket_exemptions": exemptions,
        "review_metadata": {
            "reviewer": reviewer.strip(), "reviewed_on": reviewed_on,
            "exported_at": now(), "attestation_checked": True,
            "attestation_statement": ATTESTATION_STATEMENT,
            "source_ruleset": session["source"]["ruleset"],
            "audit_entries": sum(len(item["audit"]) for item in session["items"]),
            "notice": "Attestation records a claim; it is not cryptographic proof of human review.",
        },
    }
    atomic_json(output, export)
    return report


def handler(store: SessionStore, actor: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: object) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def _asset(self, filename: str, content_type: str) -> None:
            try:
                body = (DASHBOARD_ROOT / filename).read_bytes()
            except OSError:
                self._json(500, {"error": "dashboard asset is unavailable"}); return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'self'; style-src 'self'; "
                             "img-src 'self' https: data:; connect-src 'self'; base-uri 'none'; "
                             "form-action 'self'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def _allowed_origin(self) -> str | None:
            host = self.headers.get("Host", "")
            allowed = {f"127.0.0.1:{self.server.server_port}",
                       f"localhost:{self.server.server_port}"}
            return f"http://{host}" if host in allowed else None

        def _protect(self, mutation: bool = False) -> bool:
            origin = self._allowed_origin()
            if origin is None:
                self._json(400, {"error": "invalid Host header"}); return False
            if mutation:
                if self.headers.get("Origin") != origin:
                    self._json(403, {"error": "cross-origin mutation rejected"}); return False
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    self._json(415, {"error": "application/json required"}); return False
                session = store.read()
                if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""),
                                           session["csrf_token"]):
                    self._json(403, {"error": "invalid CSRF token"}); return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            if not self._protect():
                return
            parsed = urlparse(self.path)
            if parsed.path in DASHBOARD_ASSETS:
                filename, content_type = DASHBOARD_ASSETS[parsed.path]
                self._asset(filename, content_type); return
            if parsed.path == "/api/session":
                session = store.read()
                items = []
                for item in session["items"]:
                    public = {key: item[key] for key in (
                        "id", "source", "review", "revision", "feedback",
                        "feedback_revision")}
                    public["selection_notice"] = "Selection context is hidden until predictions are revealed."
                    items.append(public)
                self._json(200, {"items": items, "progress": progress(session, store.rules),
                                 "revision": session["revision"],
                                 "csrf_token": session["csrf_token"],
                                 "rare_bucket_exemptions": session.get("rare_bucket_exemptions", {}),
                                 "vocabulary": {
                                     "buckets": [{"name": rule.name, "group": rule.group,
                                                  "subtypes": list(rule.subtypes)}
                                                 for rule in store.rules.buckets],
                                     "evidence_kinds": sorted(EVIDENCE_KINDS),
                                     "critical_assertions": sorted(REQUIRED_CRITICAL),
                                     "feedback_dispositions": sorted(FEEDBACK_DISPOSITIONS),
                                     "feedback_reasons": sorted(FEEDBACK_REASONS),
                                     "subtypes": sorted({subtype for rule in store.rules.buckets
                                                         for subtype in rule.subtypes}),
                                 }}); return
            if parsed.path.startswith("/api/item/") and parsed.path.endswith("/prediction"):
                try:
                    item_id = decode_item_id(parsed.path[len("/api/item/"):-len("/prediction")])
                except ReviewError as exc:
                    self._json(400, {"error": str(exc)}); return
                session = store.read()
                item = next((row for row in session["items"] if row["id"] == item_id), None)
                if item is None:
                    self._json(404, {"error": "unknown review item"}); return
                self._json(200, {"id": item["id"], "prediction": item["prediction"],
                                 "selection_keys": item["selection_keys"]}); return
            if parsed.path == "/api/feedback-export.json":
                payload = feedback_export(store.read())
                body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Disposition", "attachment; filename=gold-review-feedback.json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._protect(mutation=True):
                return
            parts = urlparse(self.path).path.split("/")
            if urlparse(self.path).path == "/api/exemptions":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 1 or length > 1_000_000:
                        raise ReviewError("invalid request size")
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict) or set(body) != {"rare_bucket_exemptions", "expected_revision"}:
                        raise ReviewError("body must contain exemptions and expected_revision")
                    result = store.update_exemptions(body["rare_bucket_exemptions"], actor,
                                                     body["expected_revision"])
                    self._json(200, {"rare_bucket_exemptions": result})
                except ConflictError as exc:
                    self._json(409, {"error": str(exc)})
                except (ReviewError, json.JSONDecodeError, ValueError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if len(parts) == 4 and parts[1:3] == ["api", "feedback"] and parts[3]:
                try:
                    item_id = decode_item_id(parts[3])
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 1 or length > 1_000_000:
                        raise ReviewError("invalid request size")
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict) or set(body) != {"feedback", "expected_revision"}:
                        raise ReviewError("body must contain feedback and expected_revision")
                    item = store.update_feedback(item_id, body["feedback"], actor,
                                                 body["expected_revision"])
                    self._json(200, {"item": {"id": item["id"],
                                               "feedback": item["feedback"],
                                               "feedback_revision": item["feedback_revision"]}})
                except ConflictError as exc:
                    self._json(409, {"error": str(exc)})
                except (ReviewError, json.JSONDecodeError, ValueError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if len(parts) != 4 or parts[1:3] != ["api", "item"] or not parts[3]:
                self._json(404, {"error": "not found"}); return
            try:
                item_id = decode_item_id(parts[3])
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 1_000_000:
                    raise ReviewError("invalid request size")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {"review", "expected_revision"}:
                    raise ReviewError("body must contain review and expected_revision")
                item = store.update(item_id, body["review"], actor, body["expected_revision"])
                self._json(200, {"item": {"id": item["id"], "review": item["review"],
                                           "revision": item["revision"]}})
            except ConflictError as exc:
                self._json(409, {"error": str(exc)})
            except (ReviewError, json.JSONDecodeError, ValueError) as exc:
                self._json(400, {"error": str(exc)})

        def log_message(self, format: str, *args: object) -> None:
            return
    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--buckets", type=Path, default=Path("buckets.yaml"))
    common.add_argument("--profile", type=Path, default=Path("profile.yaml"))
    generate = sub.add_parser("generate", parents=[common])
    generate.add_argument("--raw", type=Path, required=True)
    generate.add_argument("--output", type=Path, default=Path("data/review/review_session.json"))
    generate.add_argument("--legacy", type=Path); generate.add_argument("--reviewer", required=True)
    generate.add_argument("--per-stratum", type=int, default=2)
    serve = sub.add_parser("serve", parents=[common]); serve.add_argument("--session", type=Path, required=True)
    serve.add_argument("--reviewer", required=True); serve.add_argument("--host", default="127.0.0.1"); serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true")
    export = sub.add_parser("export", parents=[common]); export.add_argument("--session", type=Path, required=True)
    export.add_argument("--output", type=Path,
                        default=Path("data/review/deterministic_classification_gold.json"))
    export.add_argument("--reviewer", required=True); export.add_argument("--reviewed-on", required=True)
    export.add_argument("--attest-human-review", action="store_true",
                        help=ATTESTATION_STATEMENT)
    export.add_argument("--allow-test-fixture", action="store_true",
                        help="allow an intentional export under tests/fixtures")
    args = parser.parse_args(argv)
    try:
        rules = load_rules(args.buckets, args.profile)
        if args.command == "generate":
            session = generate_session(args.raw, args.output, rules, args.reviewer,
                                       args.legacy, args.per_stratum,
                                       protected_paths=[args.buckets, args.profile])
            print(f"Selected {len(session['items'])} strict products from {session['sampling']['products_seen']}; no labels were assigned.")
            print(f"Session: {args.output}")
            return 0
        if args.command == "serve":
            if args.host not in {"127.0.0.1", "localhost"}:
                raise ReviewError("review server must bind to IPv4 loopback (127.0.0.1 or localhost)")
            session = load_session(args.session, rules)
            if args.reviewer.strip() != session["reviewer"]:
                raise ReviewError("reviewer must match the session reviewer")
            server = ThreadingHTTPServer((args.host, args.port), handler(SessionStore(args.session, rules), args.reviewer))
            url = f"http://{args.host}:{server.server_port}/"; print(f"Review UI: {url}")
            if args.open: webbrowser.open(url)
            server.serve_forever(); return 0
        report = export_gold(args.session, args.output, rules, args.reviewer,
                             args.reviewed_on, args.attest_human_review,
                             protected_paths=[args.buckets, args.profile],
                             allow_test_fixture=args.allow_test_fixture)
        print(json.dumps(report, indent=2, sort_keys=True))
        print("This result is self-consistency evidence; attestation is not proof that review was human.")
        return 0 if report["accuracy_gates_passed"] else 1
    except (ConfigError, PipelineError, ReviewError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=os.sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
