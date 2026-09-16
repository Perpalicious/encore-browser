#!/usr/bin/env python3
"""
The recall legend: a short list of the search terms the user tends to forget.

    python3 tools/recall_legend.py build      # recall_legend.yaml -> viewer JSON
    python3 tools/recall_legend.py suggest    # what the bid history says is missing

`recall_legend.yaml` (repo root) is the source of truth and is hand-curated:
natural search phrases ("clamps", "tie downs", "hand vacuum"), grouped roughly
by the `buckets.yaml` groups. `build` validates it and writes
`viewer/src/data/recall_legend.json`, which the viewer imports statically —
so commit both files together. The viewer treats a term as nothing more than
a string to drop into the search box.

`suggest` reads `data/Watch/history.tsv` (gitignored; see
`data/Watch/FINDINGS.md` for how it is kept) and prints the product phrases
that were bid on or watched but are not covered by any term already in the
YAML. It seeded the first version of the file and is the thing to run after
appending a new batch of history. The heuristic is deliberately crude — it
proposes, a person decides. The user's own examples were never the source.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

LEGEND_PATH = Path("recall_legend.yaml")
JSON_PATH = Path("viewer/src/data/recall_legend.json")
HISTORY_PATH = Path("data/Watch/history.tsv")

# Words that never make a search term on their own.
_STOP = {
    "AND", "FOR", "WITH", "THE", "OF", "IN", "TO", "PACK", "SET", "PC", "PCS",
    "PK", "KIT", "NEW", "BOX", "CASE", "LOT", "ASSORTED", "PIECE", "PIECES",
    "SIZE", "COLOR", "COLOUR", "BLACK", "WHITE", "GREY", "GRAY", "BLUE", "RED",
    "GREEN", "PINK", "LARGE", "SMALL", "MEDIUM", "MENS", "WOMENS", "KIDS",
    "INCH", "IN", "FT", "CM", "MM", "OZ", "LB", "LBS", "GAL", "ML", "PRO",
    "PLUS", "MAX", "ULTRA", "MINI", "ORIGINAL", "STYLE", "TYPE", "DUAL",
}


# --- legend file ------------------------------------------------------------

def load_legend(path: Path = LEGEND_PATH) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(groups, list):
        raise ValueError(f"{path}: expected a top-level `groups:` list")
    return groups


def validate(groups: list[dict]) -> list[str]:
    """Problems that would ship a broken or misleading legend."""
    problems: list[str] = []
    seen: dict[str, str] = {}
    for i, group in enumerate(groups, 1):
        name = (group.get("name") or "").strip() if isinstance(group, dict) else ""
        if not name:
            problems.append(f"group #{i}: missing name")
            name = f"#{i}"
        terms = group.get("terms") if isinstance(group, dict) else None
        if not isinstance(terms, list) or not terms:
            problems.append(f"{name}: no terms")
            continue
        for term in terms:
            if not isinstance(term, str) or not term.strip():
                problems.append(f"{name}: empty term")
                continue
            key = term.strip().lower()
            if key in seen:
                problems.append(f"{name}: '{term}' duplicates a term in {seen[key]}")
            seen[key] = name
    return problems


def to_json(groups: list[dict]) -> dict:
    return {"groups": [
        {"name": g["name"].strip(), "terms": [t.strip() for t in g["terms"]]}
        for g in groups
    ]}


def all_terms(groups: list[dict]) -> list[str]:
    return [t.strip().lower() for g in groups for t in (g.get("terms") or []) if isinstance(t, str)]


# --- history ------------------------------------------------------------------

def read_history(path: Path = HISTORY_PATH) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _is_line_code(word: str) -> bool:
    # Same rule as tools/recall_check.py: short tokens and anything with a
    # digit are model numbers, sizes or quantities, never product words.
    return len(word) <= 2 or any(ch.isdigit() for ch in word)


def title_phrases(title: str) -> list[str]:
    """The product phrases a title suggests, brand stripped: the two words
    after the brand and the single word after it. "SHARK WANDVAC HANDHELD
    VACUUM" -> ["wandvac handheld", "wandvac"]."""
    tokens = re.sub(r"[^A-Z0-9 ]", " ", (title or "").upper()).split()
    words = [t for t in tokens if not _is_line_code(t) and t not in _STOP]
    if len(words) >= 3:
        words = words[1:]  # leading word is the brand more often than not
    phrases: list[str] = []
    if len(words) >= 2:
        phrases.append(f"{words[0]} {words[1]}".lower())
    if words:
        phrases.append(words[0].lower())
    return phrases


def candidate_terms(rows: list[dict]) -> dict[str, dict[str, int]]:
    """phrase -> {"bid": n, "watch": n} over every history row."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"bid": 0, "watch": 0})
    for row in rows:
        signal = (row.get("signal") or "").strip().lower()
        if signal not in ("bid", "watch"):
            continue
        for phrase in title_phrases(row.get("title") or ""):
            counts[phrase][signal] += 1
    return counts


def uncovered(candidates: dict[str, dict[str, int]], terms: list[str]) -> list[tuple[str, int, int, int]]:
    """Candidates no legend term already covers (substring either way),
    scored 2*bids + watches, best first."""
    lowered = [t.lower() for t in terms]
    out = []
    for phrase, c in candidates.items():
        if any(t in phrase or phrase in t for t in lowered):
            continue
        out.append((phrase, c["bid"], c["watch"], 2 * c["bid"] + c["watch"]))
    return sorted(out, key=lambda r: (-r[3], r[0]))


# --- commands -----------------------------------------------------------------

def build() -> None:
    groups = load_legend()
    problems = validate(groups)
    if problems:
        sys.exit("recall_legend.yaml has problems:\n  " + "\n  ".join(problems))
    payload = to_json(groups)
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    n_terms = sum(len(g["terms"]) for g in payload["groups"])
    print(f"{len(payload['groups'])} groups, {n_terms} terms -> {JSON_PATH}")


def suggest(limit: int = 80) -> None:
    if not HISTORY_PATH.exists():
        sys.exit(f"{HISTORY_PATH} not found — it is local-only; see data/Watch/FINDINGS.md")
    groups = load_legend() if LEGEND_PATH.exists() else []
    rows = read_history()
    ranked = uncovered(candidate_terms(rows), all_terms(groups))
    print(f"{len(rows)} history rows, {len(ranked)} phrases not covered by the "
          f"{len(all_terms(groups))} legend terms. Top {limit} (score = 2*bids + watches):\n")
    print(f"{'phrase':34s} {'bids':>4s} {'watch':>5s} {'score':>5s}")
    for phrase, bids, watches, score in ranked[:limit]:
        print(f"{phrase:34s} {bids:>4d} {watches:>5d} {score:>5d}")


def main(argv: list[str]) -> None:
    if argv == ["build"]:
        build()
    elif argv == ["suggest"]:
        suggest()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
