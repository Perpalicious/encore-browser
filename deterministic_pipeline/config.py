"""Strictly validated deterministic rules loaded from repository YAML."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scraper.condition import CONDITION_LABELS


class ConfigError(ValueError):
    """Configuration is malformed or internally inconsistent."""


@dataclass(frozen=True)
class BucketRule:
    name: str
    group: str
    include_any: tuple[str, ...]
    exclude_any: tuple[str, ...]
    categories: tuple[str, ...]
    condition_in: tuple[str, ...]
    subtypes: tuple[str, ...]
    brand_terms: tuple[str, ...]


@dataclass(frozen=True)
class InterestRule:
    name: str
    buckets: tuple[str, ...]
    tags: tuple[str, ...]
    include_any: tuple[str, ...]


@dataclass(frozen=True)
class ProvenResaleRule:
    product: str
    include_any: tuple[str, ...]
    exclude_any: tuple[str, ...]


@dataclass(frozen=True)
class PersonalGates:
    reject_conditions: tuple[str, ...]
    reject_functional: tuple[str, ...]
    reject_missing_major_parts: tuple[str, ...]
    apparel_sizes: tuple[tuple[str, str], ...]
    shoe_size: str | None
    generic_accessory_terms: tuple[str, ...]


@dataclass(frozen=True)
class ProjectRule:
    project: str
    buckets: tuple[str, ...]


@dataclass(frozen=True)
class Rules:
    buckets: tuple[BucketRule, ...]
    interests: tuple[InterestRule, ...]
    projects: tuple[ProjectRule, ...]
    not_wanted: tuple[str, ...]
    proven_resale: tuple[ProvenResaleRule, ...]
    personal_gates: PersonalGates
    ruleset: str


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a mapping")
    return value


def _strings(value: Any, where: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None:
        if required:
            raise ConfigError(f"{where} must be a nonempty list of strings")
        return ()
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ConfigError(f"{where} must be a list of nonempty strings")
    values = tuple(value)
    if required and not values:
        raise ConfigError(f"{where} must be a nonempty list of strings")
    if len(set(values)) != len(values):
        raise ConfigError(f"{where} contains duplicate values")
    return values


def _name(raw: dict[str, Any], where: str) -> str:
    value = raw.get("name")
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}.name must be a nonempty string")
    return value


def _reject_unknown(raw: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError(f"{where} has unsupported keys: {sorted(unknown)}")


def _load_yaml(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read {label}: {path}: {exc}") from exc
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {label}: {exc}") from exc
    return content, _mapping(parsed, label)


def load_rules(bucket_path: Path, profile_path: Path) -> Rules:
    bucket_bytes, bucket_doc = _load_yaml(bucket_path, "buckets.yaml")
    profile_bytes, profile_doc = _load_yaml(profile_path, "profile.yaml")
    _reject_unknown(bucket_doc, {"buckets"}, "buckets.yaml")
    _reject_unknown(profile_doc, {"sizes", "projects", "not_wanted", "interests",
                                  "deterministic", "proven_resale"}, "profile.yaml")
    raw_buckets = bucket_doc.get("buckets")
    raw_interests = profile_doc.get("interests")
    if not isinstance(raw_buckets, list) or not raw_buckets:
        raise ConfigError("buckets.yaml.buckets must be a nonempty list")
    if not isinstance(raw_interests, list) or not raw_interests:
        raise ConfigError("profile.yaml.interests must be a nonempty list")

    buckets: list[BucketRule] = []
    bucket_names: set[str] = set()
    for index, value in enumerate(raw_buckets):
        raw = _mapping(value, f"buckets[{index}]")
        _reject_unknown(raw, {"name", "group", "description", "examples", "subtypes",
                              "seeds", "include_any", "exclude", "exclude_any", "categories",
                              "aliases", "seed_exempt", "condition_in"}, f"buckets[{index}]")
        name = _name(raw, f"buckets[{index}]")
        if "seeds" in raw and "include_any" in raw:
            raise ConfigError(f"{name} cannot define both seeds and include_any")
        if "exclude" in raw and "exclude_any" in raw:
            raise ConfigError(f"{name} cannot define both exclude and exclude_any")
        if name in bucket_names:
            raise ConfigError(f"duplicate bucket name: {name}")
        bucket_names.add(name)
        group = raw.get("group")
        if not isinstance(group, str) or not group.strip():
            raise ConfigError(f"{name}.group must be a nonempty string")
        conditions = _strings(raw.get("condition_in"), f"{name}.condition_in")
        unknown = set(conditions) - set(CONDITION_LABELS)
        if unknown:
            raise ConfigError(f"{name}.condition_in has unknown values: {sorted(unknown)}")
        includes = _strings(raw.get("include_any", raw.get("seeds")), f"{name}.include_any")
        categories = _strings(raw.get("categories"), f"{name}.categories")
        if not includes and not categories:
            raise ConfigError(f"{name} needs include_any/seeds or categories")
        excludes = _strings(raw.get("exclude_any", raw.get("exclude")), f"{name}.exclude_any")
        conflict = {term.casefold().strip() for term in includes} & {
            term.casefold().strip() for term in excludes}
        if conflict:
            raise ConfigError(f"{name} includes and excludes the same terms: {sorted(conflict)}")
        buckets.append(BucketRule(
            name=name, group=group, include_any=includes,
            exclude_any=excludes,
            categories=categories, condition_in=conditions,
            subtypes=_strings(raw.get("subtypes"), f"{name}.subtypes", required=True),
            brand_terms=_strings(raw.get("examples"), f"{name}.examples"),
        ))

    interests: list[InterestRule] = []
    interest_names: set[str] = set()
    claimed_buckets: set[str] = set()
    for index, value in enumerate(raw_interests):
        raw = _mapping(value, f"interests[{index}]")
        _reject_unknown(raw, {"name", "buckets", "tags", "description", "seeds"},
                        f"interests[{index}]")
        name = _name(raw, f"interests[{index}]")
        if name in interest_names:
            raise ConfigError(f"duplicate interest name: {name}")
        interest_names.add(name)
        refs = _strings(raw.get("buckets"), f"{name}.buckets")
        missing = set(refs) - bucket_names
        if missing:
            raise ConfigError(f"{name} references unknown buckets: {sorted(missing)}")
        claimed_buckets.update(refs)
        tags = _strings(raw.get("tags"), f"{name}.tags", required=True)
        if any(not tag.replace("_", "").isalnum() or tag.lower() != tag for tag in tags):
            raise ConfigError(f"{name}.tags must use lowercase controlled identifiers")
        seeds = _strings(raw.get("seeds"), f"{name}.seeds")
        if not refs and not seeds:
            raise ConfigError(f"{name} needs buckets or seeds")
        interests.append(InterestRule(name, refs, tags, seeds))
    unclaimed = bucket_names - claimed_buckets
    if unclaimed:
        raise ConfigError(f"buckets claimed by no profile interest: {sorted(unclaimed)}")

    project_names = _strings(profile_doc.get("projects"), "profile.yaml.projects", required=True)
    not_wanted = _strings(profile_doc.get("not_wanted"), "profile.yaml.not_wanted", required=True)
    sizes = _mapping(profile_doc.get("sizes"), "profile.yaml.sizes")
    _reject_unknown(sizes, {"apparel", "shoe"}, "profile.yaml.sizes")
    apparel = _mapping(sizes.get("apparel"), "profile.yaml.sizes.apparel")
    _reject_unknown(apparel, {"womens", "mens"}, "profile.yaml.sizes.apparel")
    apparel_sizes: list[tuple[str, str]] = []
    for audience, value in apparel.items():
        if not isinstance(audience, str) or not isinstance(value, str) or not value.strip():
            raise ConfigError("profile.yaml.sizes.apparel must map strings to nonempty strings")
        apparel_sizes.append((audience, value))
    shoe_size = sizes.get("shoe")
    if shoe_size is not None and not isinstance(shoe_size, (str, int, float)):
        raise ConfigError("profile.yaml.sizes.shoe must be a string, number, or null")

    deterministic = _mapping(profile_doc.get("deterministic"), "profile.yaml.deterministic")
    _reject_unknown(deterministic, {"project_buckets", "hard_gates"},
                    "profile.yaml.deterministic")
    raw_projects = _mapping(deterministic.get("project_buckets"),
                            "profile.yaml.deterministic.project_buckets")
    projects: list[ProjectRule] = []
    for project, refs_value in raw_projects.items():
        if project not in project_names:
            raise ConfigError(f"project_buckets has unknown project: {project}")
        refs = _strings(refs_value, f"project_buckets.{project}", required=True)
        missing = set(refs) - bucket_names
        if missing:
            raise ConfigError(f"project {project} references unknown buckets: {sorted(missing)}")
        projects.append(ProjectRule(project, refs))
    if not projects:
        raise ConfigError("profile.yaml.deterministic.project_buckets must not be empty")
    raw_gates = _mapping(deterministic.get("hard_gates"), "profile.yaml.deterministic.hard_gates")
    _reject_unknown(raw_gates, {"reject_conditions", "reject_functional",
                                "reject_missing_major_parts", "generic_accessory_terms"},
                    "profile.yaml.deterministic.hard_gates")
    reject_conditions = _strings(raw_gates.get("reject_conditions"),
                                 "hard_gates.reject_conditions", required=True)
    unknown_reject = set(reject_conditions) - set(CONDITION_LABELS)
    if unknown_reject:
        raise ConfigError(f"hard_gates.reject_conditions has unknown values: {sorted(unknown_reject)}")
    gates = PersonalGates(
        reject_conditions=reject_conditions,
        reject_functional=_strings(raw_gates.get("reject_functional"),
                                   "hard_gates.reject_functional", required=True),
        reject_missing_major_parts=_strings(raw_gates.get("reject_missing_major_parts"),
                                            "hard_gates.reject_missing_major_parts", required=True),
        apparel_sizes=tuple(sorted(apparel_sizes)),
        shoe_size=None if shoe_size is None else str(shoe_size),
        generic_accessory_terms=_strings(raw_gates.get("generic_accessory_terms"),
                                         "hard_gates.generic_accessory_terms", required=True),
    )

    raw_resale = profile_doc.get("proven_resale")
    if not isinstance(raw_resale, list):
        raise ConfigError("profile.yaml.proven_resale must be a list")
    resale: list[ProvenResaleRule] = []
    products: set[str] = set()
    for index, value in enumerate(raw_resale):
        raw = _mapping(value, f"proven_resale[{index}]")
        _reject_unknown(raw, {"product", "seeds", "exclude", "note"},
                        f"proven_resale[{index}]")
        product = raw.get("product")
        if not isinstance(product, str) or not product.strip():
            raise ConfigError(f"proven_resale[{index}].product must be a nonempty string")
        if product in products:
            raise ConfigError(f"duplicate proven_resale product: {product}")
        products.add(product)
        resale.append(ProvenResaleRule(
            product,
            _strings(raw.get("seeds"), f"{product}.seeds", required=True),
            _strings(raw.get("exclude"), f"{product}.exclude", required=True),
        ))

    digest = hashlib.sha256(bucket_bytes + b"\0" + profile_bytes).hexdigest()[:20]
    return Rules(tuple(buckets), tuple(interests), tuple(projects), not_wanted,
                 tuple(resale), gates,
                 f"rules-v2:{digest}")
