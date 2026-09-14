# Deterministic classifier baseline — 2026-09-14

No tracked raw scrape exists for this week. This baseline used an ad hoc
temporary raw-shaped fixture derived from the 28,034 records in
`viewer/src/data/auction_bundle.json`: `category_path` was copied to a joined
`hibid_category_path`, while existing title, condition and structured fields
were retained. It is reproducible only while that tracked bundle remains
unchanged; it is not claimed as a direct CLI run over the viewer envelope.
Bucket pairs were compared by lot number with the bundle's prior generated
labels. Those labels came from a model and changed between runs, so the numbers
measure disagreement to review, not accuracy against human truth.

| Measurement | Result |
| --- | ---: |
| Lots evaluated | 28,034 |
| Strict distinct products | 21,267 |
| Exact duplicate lots fanned out | 6,767 |
| Deterministic Bat lots | 9,891 |
| Deterministic personal picks | 1,137 |
| Shared bucket pairs | 7,683 |
| Deterministic-only bucket pairs | 3,243 |
| Legacy-only bucket pairs | 4,398 |
| Pair precision agreement | 70.32% |
| Pair recall agreement | 63.60% |
| Wall time | 10.45 seconds |
| Peak process RSS | 151,760 KiB |
| Classifier model/network client imports | none (source guarantee) |

The strongest agreement among meaningful-volume buckets includes Keyboards &
PC peripherals (93% precision agreement, 96% recall agreement), Home gym &
weightlifting (99%, 77%), Bedding & pillows (90%, 93%), and Hair styling tools
(98%, 80%). Large review gaps remain in Sports & recreation gear (84%, 24%),
Hand tools (34%, 25%), Smart home (60%, 30%), and Electronics (53%, 76%).

The tightened subtype matcher left 4,980 matched lots without enough title evidence for a
controlled subtype and marked them `subtype_not_proven`. It withheld a Bat
bucket on broad brand-only evidence, including 150 Kitchen appliance, 133
vacuum, 132 oral-care, and 116 Electronics candidates. These records remain
searchable and their provenance explains the unresolved decision.

The 98% micro-precision and 95% micro-recall cutover gates have not been
tested because no human-reviewed gold set exists. Before production cutover,
Bat must review a versioned set containing positives and near-negatives across
all 62 buckets. Run it with:

```bash
python -m deterministic_pipeline.evaluate \
  --gold tests/fixtures/deterministic_classification_gold.json \
  --output data/categorized/gold_report.json
```

The gold file is an object with `items` and `rare_bucket_exemptions`. Every row
records expected and forbidden buckets, expected subtype and provenance kinds,
personal expectation, critical assertions, and a human rationale. The
evaluator requires 20 positive and 20 near-negative examples per bucket. A
rare-bucket exemption must justify smaller nonzero minimums explicitly. It
returns nonzero when coverage, aggregate, per-bucket, subtype, provenance,
personal hard-gate, critical, or forbidden-match gates fail.

The final synthetic scale benchmark classified 25,000 rows in 12.34 seconds
and 100,000 rows in 51.78 seconds, a 4.20× time increase for 4× the input. Peak
RSS was 36,000 KiB. The benchmark source imports no model or network client and
reports a stable output checksum.
