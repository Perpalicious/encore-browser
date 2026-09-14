"""Deterministic, multi-label bucket and personal-interest classifier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .config import BucketRule, Rules
from .normalize import canonical_record, normalize_category, normalize_text


@lru_cache(maxsize=None)
def _pattern(term: str) -> re.Pattern[str]:
    # Preserve the prefilter's intentional convention: a trailing space asks
    # for a right word boundary; all terms have a left word boundary.
    right_boundary = term != term.rstrip()
    value = normalize_text(term.strip())
    escaped = re.escape(value).replace(r"\ ", r"\s+")
    return re.compile(r"(?<!\w)" + escaped + (r"(?!\w)" if right_boundary else ""))


@lru_cache(maxsize=None)
def _combined_pattern(terms: tuple[str, ...]) -> re.Pattern[str] | None:
    parts: list[str] = []
    for term in sorted(terms, key=lambda value: (-len(value.strip()), value)):
        if not term.strip():
            continue
        right_boundary = term != term.rstrip()
        escaped = re.escape(normalize_text(term.strip())).replace(r"\ ", r"\s+")
        parts.append(r"(?<!\w)" + escaped + (r"(?!\w)" if right_boundary else ""))
    return re.compile("(?:" + "|".join(parts) + ")") if parts else None


def _first_hit(terms: tuple[str, ...], text: str) -> str | None:
    pattern = _combined_pattern(terms)
    match = pattern.search(text) if pattern else None
    return match.group(0) if match else None


def _category_hit(configured: tuple[str, ...], actual: tuple[str, ...]) -> str | None:
    for raw in configured:
        wanted = normalize_category(raw)
        if wanted and actual[:len(wanted)] == wanted:
            return raw
    return None


def _word_forms(word: str) -> set[str]:
    irregular = {"mice": {"mice", "mouse"}, "knives": {"knives", "knife"}}
    if word in irregular:
        return irregular[word]
    forms = {word}
    if word.endswith("ies") and len(word) > 4:
        forms.add(word[:-3] + "y")
    elif word.endswith("s") and len(word) > 3:
        forms.add(word[:-1])
    return forms


def _subtype(rule: BucketRule, text: str) -> tuple[str | None, dict | None]:
    title_words = set(re.findall(r"[\w+]+", text))
    candidates: list[tuple[int, int, str, dict[str, str]]] = []
    for index, subtype in enumerate(rule.subtypes):
        normalized = normalize_text(subtype)
        if normalized == "kb+mouse combos":
            keyboard = "keyboard" in title_words or "kb" in title_words
            if keyboard and "mouse" in title_words and ({"combo", "combos", "set"} & title_words):
                candidates.append((3, -index, subtype,
                                   {"kind": "subtype_terms", "value": "keyboard mouse combo"}))
            continue
        words = [w for w in normalized.split() if len(w) >= 3 and w not in {"and", "the"}]
        if not words:
            continue
        if " and " in f" {normalized} ":
            # "wrenches & sockets" names alternatives; one exact product noun
            # is enough. Exact inflection prevents `key` matching `keyboard`.
            matched = next((word for word in words if _word_forms(word) & title_words), None)
            if matched:
                candidates.append((1, -index, subtype,
                                   {"kind": "subtype_terms", "value": matched}))
            continue
        matched_words = [word for word in words if _word_forms(word) & title_words]
        if len(matched_words) == len(words):
            exact_component = 100 if normalized in {"key switches", "keycaps"} else 0
            candidates.append((exact_component + len(words), -index, subtype,
                               {"kind": "subtype_terms", "value": " ".join(words)}))
    if not candidates:
        return None, None
    _, _, subtype, evidence = max(candidates)
    return subtype, evidence


@dataclass(frozen=True)
class Classification:
    row: dict[str, Any]
    provenance: dict[str, Any]


class DeterministicClassifier:
    def __init__(self, rules: Rules):
        self.rules = rules
        self._bucket_prefix: dict[str, set[int]] = {}
        self._category_rules: set[int] = set()
        for index, rule in enumerate(rules.buckets):
            if rule.categories:
                self._category_rules.add(index)
            for term in rule.include_any:
                words = normalize_text(term.strip()).split()
                if words:
                    self._bucket_prefix.setdefault(words[0], set()).add(index)
        self._interest_prefix: dict[str, set[int]] = {}
        for index, interest in enumerate(rules.interests):
            for term in interest.include_any:
                words = normalize_text(term.strip()).split()
                if words:
                    self._interest_prefix.setdefault(words[0], set()).add(index)

    @staticmethod
    def _candidate_indexes(text: str, prefixes: dict[str, set[int]]) -> set[int]:
        candidates: set[int] = set()
        for token in text.split():
            # Seeds match at a left word boundary and may match a plural or
            # compound suffix, so every prefix of this word is relevant.
            for end in range(2, len(token) + 1):
                candidates.update(prefixes.get(token[:end], ()))
        return candidates

    def classify(self, lot: dict[str, Any]) -> Classification:
        normalized = canonical_record(lot)
        # Description is excluded from positive matching: unrelated prose must
        # not manufacture a classification. Structured title/model/category do.
        text = " ".join(filter(None, (normalized["title"], normalized["model"],
                                      normalized["size"], normalized["notes"])))
        condition = normalized["condition"]
        decisions: list[dict[str, Any]] = []
        matched: list[tuple[BucketRule, list[dict[str, str]], str | None]] = []
        unresolved: list[str] = []

        candidate_rules = self._candidate_indexes(text, self._bucket_prefix)
        candidate_rules.update(self._category_rules)
        for rule_index in sorted(candidate_rules):
            rule = self.rules.buckets[rule_index]
            exclusion = _first_hit(rule.exclude_any, text)
            if exclusion:
                decisions.append({"bucket": rule.name, "decision": "excluded",
                                  "matched_by": [{"kind": "exclude", "value": exclusion}]})
                continue
            if rule.condition_in and condition not in rule.condition_in:
                kind = "condition_missing" if not condition else "condition_gate"
                decisions.append({"bucket": rule.name, "decision": "excluded",
                                  "matched_by": [{"kind": kind, "value": condition or "missing"}]})
                if not condition:
                    unresolved.append(f"missing_condition:{rule.name}")
                continue
            seed = _first_hit(rule.include_any, text)
            category = _category_hit(rule.categories, normalized["category"])
            evidence: list[dict[str, str]] = []
            brand_values = {normalize_text(value) for value in rule.brand_terms}
            seed_is_brand = seed is not None and normalize_text(seed) in brand_values
            nonbrand_terms = tuple(term for term in rule.include_any
                                   if normalize_text(term) not in brand_values)
            nonbrand_hit = _first_hit(nonbrand_terms, text)
            if seed_is_brand and not nonbrand_hit and not category:
                decisions.append({"bucket": rule.name, "decision": "unresolved",
                                  "matched_by": [{"kind": "brand_without_product_type",
                                                  "value": seed}]})
                unresolved.append(f"brand_without_product_type:{rule.name}")
                continue
            if seed:
                evidence.append({"kind": "title_seed", "value": seed})
            if category:
                evidence.append({"kind": "category_prefix", "value": category})
            if evidence:
                subtype, subtype_evidence = _subtype(rule, text)
                if subtype_evidence:
                    evidence.append(subtype_evidence)
                matched.append((rule, evidence, subtype))
                decisions.append({"bucket": rule.name, "decision": "matched",
                                  "matched_by": evidence})

        bucket_names = [rule.name for rule, _, _ in matched]
        subtype_values = [subtype for _, _, subtype in matched if subtype]
        subtype = subtype_values[0] if subtype_values else None

        personal_tags: list[str] = []
        personal_evidence: list[dict[str, str]] = []
        personal_condition_rejected = False
        project_evidence = [
            {"kind": "active_project", "value": project.project}
            for project in self.rules.projects
            if set(project.buckets) & set(bucket_names)
        ]
        # A broad bucket describes something worth browsing, not proof Bat
        # wants this listing now. Personal picks require a profile-specific
        # term or an exact proven-resale signal.
        interest_indexes = self._candidate_indexes(text, self._interest_prefix)
        for interest_index in sorted(interest_indexes):
            interest = self.rules.interests[interest_index]
            hit = _first_hit(interest.include_any, text)
            if hit:
                bucket_by_name = {rule.name: rule for rule in self.rules.buckets}
                gates = [bucket_by_name[name].condition_in for name in interest.buckets
                         if bucket_by_name[name].condition_in]
                if gates and (not condition or not any(condition in gate for gate in gates)):
                    personal_condition_rejected = True
                    continue
                if gates and lot.get("seal_intact") is not True:
                    personal_condition_rejected = True
                    unresolved.append("personal_consumable_seal_unproven")
                    continue
                personal_tags.extend(interest.tags)
                personal_evidence.append({"kind": "profile_seed", "value": hit,
                                          "interest": interest.name})
        proven = None
        for resale in self.rules.proven_resale:
            hit = _first_hit(resale.include_any, text)
            accessory = _first_hit(resale.exclude_any, text)
            if hit and not accessory:
                proven = resale.product
                personal_tags.append("proven_resale")
                personal_evidence.append({"kind": "proven_resale", "value": hit,
                                          "product": resale.product})
                break
            if hit and accessory:
                unresolved.append(f"proven_resale_accessory:{resale.product}")

        gates = self.rules.personal_gates
        hard_reject_reasons: list[str] = []
        if condition in gates.reject_conditions:
            hard_reject_reasons.append(f"condition:{condition}")
        if str(lot.get("functional") or "") in gates.reject_functional:
            hard_reject_reasons.append(f"functional:{lot.get('functional')}")
        if str(lot.get("missing_major_parts") or "") in gates.reject_missing_major_parts:
            hard_reject_reasons.append(f"missing_major_parts:{lot.get('missing_major_parts')}")
        if lot.get("damaged") is True:
            hard_reject_reasons.append("damaged:true")
        if str(lot.get("damage") or "").strip():
            hard_reject_reasons.append("damage:reported")
        if str(lot.get("missing_parts") or "").strip():
            hard_reject_reasons.append("missing_parts:reported")
        if "Brand boots & shoes" in bucket_names:
            if gates.shoe_size is None:
                hard_reject_reasons.append("shoe_size:not_configured")
            elif normalized["size"] and normalize_text(gates.shoe_size) not in normalized["size"].split():
                hard_reject_reasons.append(f"shoe_size:{normalized['size']}")
        apparel_words = {"shirt", "jacket", "pants", "dress", "apparel", "clothing"}
        if apparel_words & set(normalized["title"].split()):
            configured_sizes = {normalize_text(value) for _, value in gates.apparel_sizes}
            if not normalized["size"] or not (configured_sizes & set(normalized["size"].split())):
                hard_reject_reasons.append(f"apparel_size:{normalized['size'] or 'missing'}")
        accessory = _first_hit(gates.generic_accessory_terms, text)
        if accessory:
            hard_reject_reasons.append(f"generic_accessory:{accessory}")
        hard_reject = bool(hard_reject_reasons)
        personal = bool(personal_evidence) and not hard_reject
        personal_tags = list(dict.fromkeys(personal_tags)) if personal else []
        row: dict[str, Any] = {
            "lot_number": str(lot.get("lot_number") or ""),
            "is_bats_list": bool(bucket_names),
            "bats_buckets": bucket_names,
            "personal_match": personal,
        }
        if subtype:
            row["bats_subtype"] = subtype
        if personal:
            row.update({
                "personal_tags": personal_tags,
                "match_strength": "strong" if proven else "moderate",
                "match_types": ["proven_resale" if proven else "personal_use"],
                "personal_reasoning": (
                    f"Matched recorded resale product: {proven}." if proven else
                    "Matched an explicit term in the local interest profile."
                ),
            })

        if bucket_names and not subtype:
            unresolved.append("subtype_not_proven")
        if bucket_names and not personal:
            unresolved.append("current_personal_intent_not_proven")
        if not normalized["title"]:
            unresolved.append("missing_title")
        if personal_condition_rejected:
            unresolved.append("personal_consumable_condition_rejected")
        unresolved.extend(f"personal_hard_gate:{reason}" for reason in hard_reject_reasons)
        provenance = {
            "lot_number": row["lot_number"],
            "ruleset": self.rules.ruleset,
            "decisions": decisions,
            "personal_evidence": personal_evidence,
            "project_evidence": project_evidence,
            "personal_hard_gates": hard_reject_reasons,
            "unresolved": unresolved,
        }
        return Classification(row=row, provenance=provenance)
