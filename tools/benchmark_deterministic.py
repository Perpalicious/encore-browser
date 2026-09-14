"""Synthetic 25k/100k benchmark for the local classifier (no network I/O)."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from deterministic_pipeline.classifier import DeterministicClassifier
from deterministic_pipeline.config import load_rules


TITLES = (
    "Mechanical gaming keyboard K{n}",
    "Shark WandVac handheld vacuum WV{n}",
    "Cordless power drill model D{n}",
    "Brand new sealed shampoo lot S{n}",
    "Plain wooden decorative shelf W{n}",
)


def benchmark(classifier: DeterministicClassifier, rows: int) -> dict:
    started = time.perf_counter()
    digest = hashlib.sha256()
    matched = 0
    for index in range(rows):
        title = TITLES[index % len(TITLES)].format(n=index % 1000)
        result = classifier.classify({
            "lot_number": str(index), "title": title,
            "condition": "Brand New - Sealed" if "shampoo" in title else "Excellent",
        }).row
        matched += result["is_bats_list"]
        digest.update(json.dumps(result, sort_keys=True, separators=(",", ":")).encode())
    return {"rows": rows, "seconds": time.perf_counter() - started,
            "matched": matched, "output_checksum": digest.hexdigest()[:20]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--baseline-rows", type=int, default=25_000)
    args = parser.parse_args()
    if args.rows <= 0 or args.baseline_rows <= 0:
        parser.error("row counts must be positive")
    classifier = DeterministicClassifier(load_rules(Path("buckets.yaml"), Path("profile.yaml")))
    baseline = benchmark(classifier, args.baseline_rows)
    large = benchmark(classifier, args.rows)
    expected_ratio = args.rows / args.baseline_rows
    actual_ratio = large["seconds"] / baseline["seconds"]
    report = {"design_guarantee": "classifier imports no model or network client",
              "baseline": baseline, "large": large,
              "expected_row_ratio": expected_ratio, "actual_time_ratio": actual_ratio,
              "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    print(json.dumps(report, indent=2, sort_keys=True))
    # Broad tripwire only: shared startup/caches make small runs sublinear; a
    # superlinear regression above 1.5x the row ratio is actionable.
    return 0 if actual_ratio <= expected_ratio * 1.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
