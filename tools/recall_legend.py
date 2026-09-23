#!/usr/bin/env python3
"""
The recall legend: the names Bat's List tends to miss.

    python3 tools/recall_legend.py build      # recall_legend.yaml -> viewer JSON
    python3 tools/recall_legend.py check      # what each term finds, and the gap it closes
    python3 tools/recall_legend.py suggest    # names in the bid history the legend lacks

`recall_legend.yaml` (repo root) is the source of truth and is hand-curated.
Its terms are NAMES: brands, product lines, distinctive item names
("stanley", "all-clad", "wandvac"). Generic item types ("tumbler", "cookware")
are Bat's List's job and it already flags them, so a chip for one reminds
nobody of anything (user decision, 2026-09-23). `build` validates the YAML
and writes `viewer/src/data/recall_legend.json`, which the viewer imports
statically — so commit both files together. The viewer treats a term as
nothing more than a string to drop into the search box, and shows this
week's match count on each chip.

`check` says what each term's search actually does:
  weeks   weekly files in data/hammer/ with a product it matches — does the
          name turn up at these auctions at all
  now     lots in this week's bundle it matches, by the viewer's own rule
          (every token a substring of title/subcategory/description/category)
  missed  of those, lots Bat's List left unflagged — the gap the chip closes
and flags `never seen` (0 weeks: misspelled, or not sold here) and `noisy`
(the substring search finds over twice what the whole-word phrase does:
"flex" finds FLEXIBLE, "ring" finds SPRING). It reports and exits 0.

`suggest` reads `data/Watch/history.tsv` (gitignored; see
`data/Watch/FINDINGS.md` for how it is kept) and prints the leading brand
words of lots bid on or watched that no legend term covers yet, with the same
columns. The heuristic is deliberately crude — it proposes, a person decides.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import yaml

LEGEND_PATH = Path("recall_legend.yaml")
JSON_PATH = Path("viewer/src/data/recall_legend.json")
HISTORY_PATH = Path("data/Watch/history.tsv")
BUNDLE_PATH = Path("viewer/src/data/auction_bundle.json")
HAMMER_DIR = Path("data/hammer")

# Words that never make a name on their own.
_STOP = {
    "AND", "FOR", "WITH", "THE", "OF", "IN", "TO", "PACK", "SET", "PC", "PCS",
    "PK", "KIT", "NEW", "BOX", "CASE", "LOT", "ASSORTED", "PIECE", "PIECES",
    "SIZE", "COLOR", "COLOUR", "BLACK", "WHITE", "GREY", "GRAY", "BLUE", "RED",
    "GREEN", "PINK", "LARGE", "SMALL", "MEDIUM", "MENS", "WOMENS", "KIDS",
    "INCH", "IN", "FT", "CM", "MM", "OZ", "LB", "LBS", "GAL", "ML", "PRO",
    "PLUS", "MAX", "ULTRA", "MINI", "ORIGINAL", "STYLE", "TYPE", "DUAL",
}

# A term is `noisy` when its substring search finds more than NOISY_RATIO
# times what the whole-word phrase does, and at least NOISY_MIN lots in all.
NOISY_RATIO = 2.0
NOISY_MIN = 5


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


# --- matching, the viewer's way -------------------------------------------------

def normalize(s: str) -> str:
    """viewer/src/lib/search.ts normalize(): strip accents, lowercase."""
    decomposed = unicodedata.normalize("NFD", s or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def tokenize(term: str) -> list[str]:
    return normalize(term.strip()).split()


def lot_text(lot: dict) -> str:
    """The text the viewer's exact search reads, from the same fields."""
    return "  ".join(normalize(x) for x in (
        lot.get("title") or "", lot.get("subcategory") or "", lot.get("lot_number") or "",
        lot.get("description") or "", " ".join(lot.get("category_path") or []),
    ))


def matches(text: str, tokens: list[str]) -> bool:
    """search.ts exactMatchLotNumbers(): every token a substring."""
    return bool(tokens) and all(t in text for t in tokens)


def phrase_pattern(tokens: list[str]) -> re.Pattern:
    """The tokens as whole words, in order and adjacent. A trailing plural is
    allowed so "squishmallow" still counts SQUISHMALLOWS as a real hit."""
    body = r"\s+".join(re.escape(t) for t in tokens)
    return re.compile(rf"(?<![a-z0-9]){body}(?:e?s)?(?![a-z0-9])")


def term_stats(terms: list[str], lots: list[dict], hammer_weeks: list[list[str]]) -> dict[str, dict]:
    """term -> {weeks, now, missed, whole} over this week's lots and the
    hammer history. `whole` is `now` counted as a whole-word phrase."""
    lot_rows = [(lot_text(l), bool(l.get("bat_buckets"))) for l in lots]
    weeks_text = [[normalize(t) for t in titles] for titles in hammer_weeks]
    out: dict[str, dict] = {}
    for term in terms:
        tokens = tokenize(term)
        pattern = phrase_pattern(tokens)
        hit_rows = [(text, flagged) for text, flagged in lot_rows if matches(text, tokens)]
        out[term] = {
            "weeks": sum(1 for titles in weeks_text if any(matches(t, tokens) for t in titles)),
            "now": len(hit_rows),
            "missed": sum(1 for _, flagged in hit_rows if not flagged),
            "whole": sum(1 for text, _ in hit_rows if pattern.search(text)),
        }
    return out


def term_flags(stats: dict) -> list[str]:
    flags = []
    if stats["weeks"] == 0:
        flags.append("never seen")
    if stats["now"] >= NOISY_MIN and stats["now"] > NOISY_RATIO * stats["whole"]:
        flags.append(f"noisy ({stats['whole']} as a word)")
    return flags


# --- data on disk -------------------------------------------------------------

def read_history(path: Path = HISTORY_PATH) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def read_bundle_lots(path: Path = BUNDLE_PATH) -> list[dict]:
    if not path.exists():
        print(f"note: {path} not found — now/missed will read 0")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["lots"] if isinstance(data, dict) else data


def read_hammer_weeks(directory: Path = HAMMER_DIR) -> list[list[str]]:
    """One list of product titles per weekly hammer file."""
    files = sorted(directory.glob("*.json")) if directory.exists() else []
    if not files:
        print(f"note: no files in {directory} — weeks will read 0")
    return [
        [p.get("title") or "" for p in json.loads(f.read_text(encoding="utf-8")).get("products") or []]
        for f in files
    ]


# --- history --------------------------------------------------------------------

def _is_line_code(word: str) -> bool:
    # Same rule as tools/recall_check.py: short tokens and anything with a
    # digit are model numbers, sizes or quantities, never names.
    return len(word) <= 2 or any(ch.isdigit() for ch in word)


def title_brand(title: str) -> str | None:
    """The leading word of a title, which is the brand more often than not:
    "SHARK WANDVAC HANDHELD VACUUM" -> "shark". None when the title opens
    with a size, a code or a filler word."""
    tokens = re.findall(r"[A-Z0-9][A-Z0-9'&.+-]*", (title or "").upper())
    if not tokens:
        return None
    first = tokens[0].strip("'.-+&")
    if _is_line_code(first) or first in _STOP:
        return None
    return first.lower()


def candidate_brands(rows: list[dict]) -> dict[str, dict[str, int]]:
    """brand -> {"bid": n, "watch": n} over every history row."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"bid": 0, "watch": 0})
    for row in rows:
        signal = (row.get("signal") or "").strip().lower()
        if signal not in ("bid", "watch"):
            continue
        brand = title_brand(row.get("title") or "")
        if brand:
            counts[brand][signal] += 1
    return counts


def uncovered(candidates: dict[str, dict[str, int]], terms: list[str]) -> list[tuple[str, int, int, int]]:
    """Candidates no legend term already covers (substring either way),
    scored 2*bids + watches, best first."""
    lowered = [t.lower() for t in terms]
    out = []
    for name, c in candidates.items():
        if any(t in name or name in t for t in lowered):
            continue
        out.append((name, c["bid"], c["watch"], 2 * c["bid"] + c["watch"]))
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


def _stats_header() -> str:
    return f"{'weeks':>5s} {'now':>5s} {'missed':>6s}"


def _stats_cells(s: dict, n_weeks: int) -> str:
    return f"{s['weeks']:>2d}/{n_weeks:<2d} {s['now']:>5d} {s['missed']:>6d}"


def check() -> None:
    groups = load_legend()
    weeks = read_hammer_weeks()
    terms = [t.strip() for t in all_terms(groups)]
    stats = term_stats(terms, read_bundle_lots(), weeks)
    n_flagged = 0
    for g in groups:
        print(f"\n{g['name']}")
        print(f"  {'term':24s} {_stats_header()}")
        for term in g.get("terms") or []:
            s = stats[term.strip().lower()]
            flags = term_flags(s)
            n_flagged += bool(flags)
            print(f"  {term.strip():24s} {_stats_cells(s, len(weeks))}  {', '.join(flags)}")
    print(f"\n{len(terms)} terms, {n_flagged} flagged. weeks = of {len(weeks)} hammer files; "
          f"missed = this week's lots Bat's List left unflagged.")


def suggest(limit: int = 60) -> None:
    if not HISTORY_PATH.exists():
        sys.exit(f"{HISTORY_PATH} not found — it is local-only; see data/Watch/FINDINGS.md")
    groups = load_legend() if LEGEND_PATH.exists() else []
    rows = read_history()
    ranked = uncovered(candidate_brands(rows), all_terms(groups))[:limit]
    weeks = read_hammer_weeks()
    stats = term_stats([name for name, *_ in ranked], read_bundle_lots(), weeks)
    print(f"{len(rows)} history rows. Top {len(ranked)} leading brand words no legend term "
          f"covers (score = 2*bids + watches):\n")
    print(f"{'name':20s} {'bids':>4s} {'watch':>5s} {'score':>5s}  {_stats_header()}")
    for name, bids, watches, score in ranked:
        s = stats[name]
        print(f"{name:20s} {bids:>4d} {watches:>5d} {score:>5d}  {_stats_cells(s, len(weeks))}  "
              f"{', '.join(term_flags(s))}")


def main(argv: list[str]) -> None:
    if argv == ["build"]:
        build()
    elif argv == ["check"]:
        check()
    elif argv == ["suggest"]:
        suggest()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
