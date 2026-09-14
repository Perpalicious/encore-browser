from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_rules
from .pipeline import PRODUCTION_BUNDLE, PipelineError, is_production_bundle, run

PUBLISHED_BUNDLE = PRODUCTION_BUNDLE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m deterministic_pipeline",
        description="Classify a saved HiBid scrape locally without model calls.")
    parser.add_argument("--auction-id", required=True)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/deterministic"))
    parser.add_argument("--build-output", type=Path,
                        help="explicitly build a non-production bundle at this path")
    parser.add_argument("--buckets", type=Path, default=Path("buckets.yaml"))
    parser.add_argument("--profile", type=Path, default=Path("profile.yaml"))
    parser.add_argument("--reference", type=Path,
                        help="optional prior labels for agreement reporting; not ground truth")
    args = parser.parse_args(argv)
    raw = args.raw or Path(f"data/raw/auction_{args.auction_id}.json")
    prefix = args.output_dir / f"auction_{args.auction_id}"
    try:
        rules = load_rules(args.buckets, args.profile)
        if args.build_output and is_production_bundle(args.build_output):
            raise PipelineError("production bundle publication is unavailable during shadow evaluation")
        bundle_path = args.build_output
        report = run(
            raw_path=raw,
            categorized_path=Path(f"{prefix}_categorized.json"),
            provenance_path=Path(f"{prefix}_provenance.json"),
            report_path=Path(f"{prefix}_report.json"),
            markdown_path=Path(f"{prefix}_report.md"),
            performance_path=Path(f"{prefix}_performance.json"),
            rules=rules, bundle_path=bundle_path,
            buckets_path=args.buckets, reference_path=args.reference)
    except (ConfigError, PipelineError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Classified {report['valid_lots']:,} lots / {report['distinct_products']:,} products")
    print(f"Bat lots: {report['bat_lots']:,}; personal picks: {report['personal_lots']:,}")
    print(f"Ruleset: {report['ruleset']}; local classifier only")
    print(f"Report: {prefix}_report.md")
    if bundle_path:
        print(f"Bundle: {bundle_path}")
    else:
        print("Shadow run only; no viewer bundle was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
