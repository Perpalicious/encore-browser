"""Canonical text and product fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


def normalize_text(value: object) -> str:
    """Return stable matching text without changing the source record."""
    text = str(value or "").replace("™", " ").replace("®", " ").replace("©", " ")
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^\w.+]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def normalize_category(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(normalize_text(part) for part in value if normalize_text(part))
    # Slim rows use this delimiter. Split before normalizing it away.
    return tuple(
        normalize_text(part) for part in str(value or "").split(" - ")
        if normalize_text(part)
    )


def canonical_record(lot: dict[str, Any]) -> dict[str, Any]:
    """Build the normalized matching view while retaining source separately."""
    category = lot.get("category_path", lot.get("category"))
    return {
        "title": normalize_text(lot.get("title")),
        "model": normalize_text(lot.get("model")),
        "size": normalize_text(lot.get("size")),
        "notes": normalize_text(lot.get("notes")),
        "description": normalize_text(lot.get("description")),
        "condition": str(lot.get("condition") or "").strip(),
        "category": normalize_category(category),
    }


def _hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def strict_fingerprint(lot: dict[str, Any]) -> str:
    normalized = canonical_record(lot)
    material = {
        "version": 1,
        "title": normalized["title"],
        "model": normalized["model"],
        "size": normalized["size"],
        "condition": normalized["condition"],
        "notes": normalized["notes"],
        "description": normalized["description"],
        "category": normalized["category"],
        "damage": normalize_text(lot.get("damage")),
        "missing_parts": normalize_text(lot.get("missing_parts")),
        "damaged": lot.get("damaged"),
        "missing_major_parts": lot.get("missing_major_parts"),
        "functional": lot.get("functional"),
        "seal_intact": lot.get("seal_intact"),
    }
    return f"strict-v1:{_hash(material)}"


def product_fingerprint(lot: dict[str, Any]) -> str:
    normalized = canonical_record(lot)
    material = {
        "version": 1,
        "title": normalized["title"],
        "model": normalized["model"],
    }
    return f"product-v1:{_hash(material)}"
