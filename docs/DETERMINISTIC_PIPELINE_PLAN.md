# Deterministic pipeline replacement plan

## Implementation status (2026-09-14)

The local pipeline now exists as `python -m deterministic_pipeline`. It reads
a saved scrape, normalizes and strictly deduplicates products, applies every
configured seed/category/exclusion/condition rule as a deterministic
multi-label classifier, fans decisions back to every lot, writes a provenance
sidecar and evidence report, and can build the viewer bundle without resale
input. `python -m deterministic_pipeline.evaluate --gold <file>` enforces the
accuracy gates below against an explicitly human-reviewed fixture.

This is a shadow implementation, not an accuracy cutover. On the current
28,034-lot viewer bundle, its bucket-pair agreement with the old generated
labels is 70.3% precision and 63.6% recall. Those old labels are inconsistent
and are not ground truth, but disagreement at that size requires review. No
reviewed 62-bucket gold set exists yet, so the 98%/95% acceptance gate has not
been demonstrated. The manual production path must remain available until Bat
reviews the gold set and the deterministic evaluator passes.

The shadow command is:

```bash
python -m deterministic_pipeline --auction-id <ID>
```

Shadow artifacts go to `data/deterministic/`, away from the manual
production files under `data/categorized/`.

The current scrape has no reliable structured seal observation. Accordingly,
consumables can receive a browse bucket from their condition gate but cannot
become personal picks unless a future reviewed input explicitly supplies
`seal_intact: true`; otherwise the report records unresolved seal evidence.

This default never writes a viewer bundle. Use `--build-output <temporary-path>`
for a disposable end-to-end build. The shadow CLI has no publication action
and rejects `viewer/src/data/auction_bundle.json` as an output. Publication
code will be designed only after a real Bat-reviewed gold fixture is committed
and reviewed. The classifier package imports no model or network client. Its
report labels comparisons with previous generated output as legacy agreement,
never as measured accuracy.

## Decision

Remove generative AI from the production pipeline. Scraping, normalization,
classification, personal-interest matching, search, ranking, and bundle
generation must run locally with deterministic Python and TypeScript code.
The same inputs, configuration, and code version must produce byte-for-byte
equivalent classification output.

This change addresses the actual scaling problem. The current bundle contains
28,034 lots and 21,280 distinct title-and-condition products. Within-auction
deduplication saves 24.1%, but the remaining products are still sent through a
semantic flagging pass and a separate resale-valuation pass. Making the chunks
smaller changes where the cost occurs; it does not remove the work or make the
answers reproducible.

The viewer's ordinary catalog, category navigation, and product search do not
depend on generated labels. They should remain useful even when every optional
interest flag is absent.

## Clarified scope

The missing automation is the middle of the existing weekly workflow:

```text
scrape -> classify into Bat buckets and personal matches -> build -> viewer
```

Today the classification arrow means manually uploading JSON chunks and
configuration to ChatGPT, downloading its responses, and handing those files
back to the repository tools. The target is one local command that performs
that arrow reproducibly. Scraping is already automated and is not the scaling
problem.

The initial replacement does not:

- scrape more fields merely because the endpoints expose them
- poll lots, bids, or watch state during a live auction
- replace Encore's watchlist or bidding interface
- publish bid history or closing prices as a new product feature
- treat old AI output as correct by definition

Existing watch and bid exports remain useful in two narrow ways. They can be
joined to the correct auction deterministically, and they provide an offline
recall test for whether the rules surfaced products that were later acted on.
That does not require live polling or adding bid histories to the viewer.

## What exists today

The repository already has most of the pieces needed for the replacement:

- The scraper collects the complete catalog and HiBid category breadcrumb.
- `tools/slim.py` normalizes the records.
- `tools/chunk_flagging.py` and `tools/slim_resale.py` group identical products.
- `buckets.yaml` contains 62 interest buckets with seeds, category claims,
  exclusions, condition gates, and subtype vocabularies.
- `profile.yaml` contains interests, projects, sizes, exclusions, and controlled
  tag vocabularies.
- `tools/prefilter.py` already implements deterministic seed, category,
  exclusion, and condition matching, plus backtest and audit reports.
- `data/Watch/FINDINGS.md` records supply and engagement measurements from
  several auctions.
- The viewer already handles lots with no Bat, personal, or resale fields.

The current AI passes do two jobs:

1. Decide whether every distinct product belongs to one or more Bat buckets,
   assign a subtype, and decide whether it is a personal pick.
2. Invent a secondhand resale range, confidence, outlook, and explanation for
   every distinct product.

The first job can become an explicit rules and ranking system. The second
cannot become deterministic without a factual price source. Generated resale
figures will therefore be removed and later replaced only by observed data,
such as closing bids, exact-product comparables, or a recorded completed sale.

## Product contract

The deterministic system must produce three independent views of a lot:

1. **Catalog facts** come directly from HiBid: title, description, category
   path, condition, images, close time, lot URL, and any available auction
   facts such as current bid or bid count.
2. **Interest classification** comes from versioned local rules: Bat buckets,
   subtype candidates, personal-interest tags, and the evidence for every
   match or rejection.
3. **User behavior**, when a same-auction local export is available, is joined
   by stable lot identity and used for evaluation or ranking. It cannot rewrite
   catalog facts. Lot numbers are reused between auctions, so a lot-number-only
   join to an older week is forbidden.

Search remains a fourth, independent operation over product fields. A query
for `keyboard` must not match a mouse merely because HiBid combines both under
`Keyboards / Mice`.

Every derived decision must include machine-readable provenance:

```json
{
  "bucket": "Keyboards & PC peripherals",
  "subtype": "mechanical keyboards",
  "matched_by": [
    {"kind": "title_seed", "value": "keyboard"},
    {"kind": "condition_gate", "value": "Excellent"}
  ],
  "ruleset": "<content hash>"
}
```

The viewer does not have to display all provenance, but the weekly report and
debug tools must make it available.

## Target pipeline

```text
HiBid scrape or saved fixture
          |
          v
schema validation -> normalization -> product fingerprinting
          |                              |
          |                              +-> exact-repeat decisions
          v
multi-label bucket rules -> personal gates -> deterministic rank
          |                    |                    |
          +--------------------+--------------------+
                               v
                     validated auction bundle
                               |
                               v
                         static viewer
```

There is no network model call and no manual chat handoff in this path.

### Normalize once

Create one canonical normalized record used by classification, search, and
tests. Normalize Unicode, whitespace, punctuation, common units, brands,
models, condition labels, category segments, and obvious title boilerplate.
Retain the untouched source values beside normalized fields for display and
debugging.

Product fingerprints should have two levels:

- **Strict:** normalized title plus condition and every available structured
  detail. This is safe for fan-out and exact historical reuse.
- **Product:** normalized brand, model, and product title without condition.
  This groups comparable listings but never transfers a condition-sensitive
  decision automatically.

Fingerprint behavior must be versioned. A normalization change invalidates
the affected cached decisions rather than silently joining different products.

### Turn prose into typed rules

Keep bucket descriptions as documentation, but do not execute prose. Extend
each bucket with typed rules whose meaning is fixed in code:

- `include_any`, `include_all`, and `exclude_any` title patterns
- exact or prefix category paths
- brand and model patterns
- allowed or rejected conditions
- structured attribute constraints such as size
- negative category and accessory rules
- subtype rules with explicit priority
- optional minimum evidence count for broad or ambiguous terms

Rules must support multi-label output. A gaming keyboard can be both
`Keyboards & PC peripherals` and `Electronics`; matching one bucket must not
stop evaluation of the others.

Broad brand names such as Logitech, Corsair, Apple, and Shark cannot establish
a product type by themselves. They require a product term, a sufficiently
specific category, or a brand-and-model rule. Exclusions run before positive
assignment and record which exclusion fired.

### Separate surfacing from personal picks

Bucket membership answers whether a product belongs in a browsable interest
area. A personal pick answers whether this particular listing is worth calling
out now. Implement these as separate deterministic stages.

Personal rules may use:

- bucket and subtype
- condition and intact-seal requirements
- configured apparel or shoe size
- active projects and `proven_resale` product identifiers
- explicit wanted and unwanted brand/model lists
- prior dismissals or completed purchases
- live price only when the source value and timestamp are present

The rules must not infer desire from auction supply. Fifty copies of a product
mean high supply, not fifty expressions of interest. Imported watches and bids
are optional ranking evidence rather than automatic positive labels because
price and condition affect those actions.

### Rank without changing classification

Use a transparent integer score only to order results. Example components are
an exact wanted model, a high-lift bucket, acceptable condition, active project,
proven resale SKU, prior dismissal, and duplicate supply. Store every component
with the score. Threshold changes may change ordering or the personal-pick
badge, but must not remove a lot from its factual category or bucket.

### Replace generated resale estimates with facts

Remove `est_resale_low`, `est_resale_high`, generated confidence, generated
outlook, and generated reasoning from the required weekly run. Until factual
comparables exist, the viewer should show no resale estimate.

A later, separately approved deterministic comparable-price module may use:

- a recorded completed resale with product fingerprint and condition
- persisted closing bid histories from the auction source
- multiple exact brand/model comparables with dates and conditions
- a documented statistic such as median and interquartile range

It must show sample count, date range, source, and matching method. A closing
bid is labeled as a closing bid, not as a completed sale. No price is produced
when the evidence threshold is unmet. This module is outside the initial
classification replacement and is not needed for cutover.

### Emit one weekly evidence report

Every run should write a compact JSON report and a readable Markdown summary:

- input lots, valid lots, rejected records, and distinct products
- exact duplicates and repeats seen in prior weeks
- counts per HiBid category, Bat bucket, subtype, and personal rule
- unmatched products and rules that matched zero products
- exclusion counts and broad rules approaching their volume limit
- engagement coverage against available local history
- config and code hashes
- runtime, peak memory, and external API cost (which must be zero)

This makes a changed result traceable to data or a rule rather than to a model
response.

## Evaluation data

Existing AI output is useful for finding cases, but it is not ground truth.
For identical title-and-condition products seen in the current bundle and a
prior bundle, the `is_bat` decision agrees only about 85-89% depending on the
week. Taxonomy and prompt changes account for some drift, but blind reuse would
also preserve previous mistakes.

Build the following versioned datasets under `tests/fixtures/`:

### Human-reviewed classification gold set

Select records across every bucket and important negative boundary:

- at least 20 positives per bucket where inventory permits
- at least 20 near-negative or accessory examples for broad buckets
- every known historical failure, including mower ignition switches,
  keyboard trays, RGB case fans, racing shifters, phone cases, and mouse-only
  search results
- cross-category positives, such as tools filed under Lawn & Garden
- consumables in every relevant condition
- repeated products with different conditions
- personal size and `not_wanted` boundary cases
- multi-label products and products with no Bat bucket

Each row contains expected buckets, allowed subtype, personal result, expected
rule evidence, and a short human rationale. Review disagreements once and
commit the resolved expectation. Rule changes that intentionally alter an
expectation must update the fixture and explain the product decision in the
commit.

### Temporal holdouts

Use whole auctions as holdouts rather than randomly splitting lots from one
auction. Repeated products make random splits leak nearly identical records
into both sides. Develop against older auctions and keep at least the newest
two labeled auctions untouched until an evaluation milestone.

### Engagement history

Use the local watch/bid history only for surfacing and ranking evaluation. The
current production-style shortlist reached 37 of 45 bids in the 2026-09-06
auction, or 82.2%. A missed bid is a useful candidate for rule review; an
unbid product is not automatically a false positive.

Join history only while the matching week's slimmed auction is available.
Require auction identity plus lot number, and verify that the exported title
is a prefix of the scraped title. The repository has measured 93.9% lot-number
overlap between different weeks, so lot number alone would produce convincing
but incorrect matches.

### Search query set

Create expected result sets for product queries such as `keyboard`, `mouse`,
`mechanical keyboard`, `monitor`, `garden hose`, and exact lot/model numbers.
Include explicit forbidden results for category contamination and fuzzy-match
collisions.

## Required tests

### Unit tests

- normalization is idempotent and preserves source values
- strict and product fingerprints distinguish condition and model correctly
- word-boundary, plural, punctuation, and hyphen behavior is documented
- inclusion, exclusion, category, brand/model, size, and condition rules
- exclusion precedence and multi-label behavior
- subtype priority and fallback behavior
- personal gates, controlled tags, and deterministic score components
- unknown condition, missing field, and malformed record behavior
- provenance contains every rule that affected the decision
- configuration schema rejects duplicate bucket names, unknown tags,
  conflicting rules, invalid conditions, and orphaned subtypes

### Regression tests

- run the complete classifier over the human-reviewed gold set
- retain a fixture for every production defect before fixing it
- compare output snapshots after sorting keys and records canonically
- fail on unexplained changes to bucket, subtype, personal flag, or evidence
- run the search query set in both exact and fuzzy modes
- verify every output bucket and tag exists in current configuration

### Property and metamorphic tests

- casing, repeated whitespace, and harmless punctuation do not change results
- adding unrelated description text does not create a title match
- changing only condition cannot change product identity
- an exclusion remains excluded when an otherwise positive brand is added
- reordering rules or input lots does not change decisions
- duplicating a lot changes quantity only, not its classification
- every emitted `is_bat` equals whether its bucket list is non-empty
- running the pipeline twice produces identical bundle and report hashes

### End-to-end tests

- saved scrape -> normalized rows -> classifications -> bundle -> viewer
- all 28,034 current lots survive exactly once in the generated bundle
- exact duplicate fan-out preserves the representative decision
- viewer remains usable with no personal picks and no resale data
- search combines correctly with category, condition, day, and bucket filters
- a keyboard search excludes mouse-only products
- static build and Playwright behavior remain unchanged for factual fields

### Performance and cost tests

Run benchmarks on the current 28,034-lot fixture and a synthetic 100,000-lot
fixture. Record wall time and peak resident memory in CI artifacts. The
classification stage must scale approximately linearly, must not make a
network request, and must incur zero external API cost. Establish the initial
wall-time and memory limits from the first implementation on Bat's normal
machine, then fail CI on a regression greater than 25% unless the limit change
is explained.

Run the fixture-free synthetic benchmark with
`python tools/benchmark_deterministic.py`. It measures 25,000 and 100,000 rows,
reports the time ratio, checksum and peak RSS, and fails on strongly
superlinear behavior without committing a large generated fixture.

## Accuracy gates

Do not replace the current published bundle until all of these hold:

- 100% schema-valid output and input-lot coverage
- 100% precision on explicit exclusion and known-defect fixtures
- at least 98% micro precision and 95% micro recall on Bat bucket labels in
  the human-reviewed set
- at least 90% recall for every bucket with 20 or more positive gold examples
- 100% recall for designated critical examples such as keyboards, active
  projects, and proven-resale SKUs
- personal-pick rules have no violations of condition, seal, size, or
  `not_wanted` hard gates
- at least 95% surfacing recall over the accumulated bid-history holdouts, or
  a reviewed explanation for every miss
- search passes every required and forbidden-result assertion
- two identical runs have identical hashes
- zero model calls and zero paid API calls

Precision and recall must be reported per bucket as well as in aggregate. A
large bucket must not hide a failed narrow bucket.

The engagement target is deliberately higher than the current measured 82.2%
baseline. If 95% cannot be reached without flooding the viewer, keep all
catalog products searchable and report recall together with candidate volume;
do not quietly weaken the target or relabel missed behavior.

## Implementation sequence

### Phase 1: freeze and measure

1. Add a command that evaluates the current rules over a saved auction without
   mutating production data.
2. Treat the existing prefilter as a candidate generator, not as a finished
   classifier. Measure both false negatives and the false-positive volume that
   the AI currently rejects after shortlisting.
3. Save baseline reports for the current bundle and available historical
   bundles.
4. Assemble and review the classification gold set and search query set.
5. Record current deterministic shortlist metrics, viewer tests, runtime, and
   candidate volume.
6. Produce a go/no-go report listing which decisions typed rules can already
   reproduce, which need additional structured rules, and which cannot be made
   from the scraped fields.

Deliverable: reproducible baseline reports and reviewed fixtures. No viewer
behavior changes.

### Phase 2: deterministic bucket classifier

1. Extract normalization and matcher behavior from `tools/prefilter.py` into
   importable modules.
2. Add a strict configuration schema and typed rule fields.
3. Generate multi-label bucket assignments, subtype, and provenance for every
   distinct product.
4. Fan the decisions back to all lots and validate total coverage.
5. Add a comparison command showing old labels, new labels, and the firing
   rules for every difference.
6. Add an `unresolved` reason for records where available fields cannot satisfy
   a bucket's evidence requirements. Unresolved records remain in catalog
   search and in their HiBid categories; they are not silently called negative.

Deliverable: a complete deterministic Bat-bucket file and accuracy report.
The existing AI-produced file remains the published input during this phase.

### Phase 3: deterministic personal matching and ranking

1. Convert profile hard gates and controlled tags into executable rules.
2. Add explicit project, wanted-product, dismissal, and proven-resale inputs.
3. Implement the explainable ranking score independently of bucket membership.
4. Evaluate against temporal engagement holdouts and review every missed bid.

Deliverable: deterministic personal flags, ordering, and evidence.

### Phase 4: remove generated resale data

1. Make all generated resale fields optional throughout build and viewer code.
2. Remove the resale prompt, handoff, expansion, and repair steps from the
   weekly runbook.
3. Replace resale filters with factual price/history controls only when those
   facts exist.
4. Preserve old bundles as historical fixtures without treating their
   generated estimates as truth.

Deliverable: a useful viewer with no fabricated price estimates and no resale
model pass.

### Phase 5: shadow run and cutover

1. Run the deterministic pipeline beside the existing output for at least two
   complete auctions.
2. Publish the per-bucket confusion report, engagement misses, search failures,
   runtime, memory, and zero-cost check after each run.
3. Resolve failures by adding a fixture first and then changing a rule.
4. Switch the build to deterministic output only after all accuracy gates pass.
5. Delete model prompts, chunk handoff code, response reconciliation, and
   runbook steps after one successful deterministic production build.

Deliverable: one-command weekly processing with no chat session or model key.

The intended command-level result is:

```text
python -m scraper ...
python -m deterministic_pipeline --auction-id <ID>
```

The second command normalizes and deduplicates the scrape, classifies every
distinct product, optionally joins a same-auction behavior export, validates
coverage, builds the viewer bundle, and writes the evidence report. It exits
non-zero before replacing the bundle when any required accuracy, schema, or
coverage check fails.

## Change discipline

Every classification change must include:

- the product behavior being changed
- at least one positive or negative fixture demonstrating it
- before-and-after aggregate and per-bucket metrics
- candidate-volume impact
- the exact configuration or code rule responsible

Do not accept screenshots or a generated answer as the sole evidence for a
rule. Keep evaluation commands read-only by default, use canonical output
ordering, and commit the small gold fixtures and reports needed to reproduce a
claim. Keep private watch/bid history out of the public repository; publish
only aggregate measurements or synthetic identifiers.

This process turns disagreements into reviewable examples. If a rule cannot be
stated, tested, and explained from the available fields, the system should
leave the product searchable and unflagged rather than manufacture an answer.
