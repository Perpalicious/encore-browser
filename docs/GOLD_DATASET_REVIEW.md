# Gold dataset review workflow

This local workflow creates the human-reviewed fixture needed to measure the
deterministic classifier. It does not call an AI service, fetch images, scrape
HiBid, modify the viewer bundle, or publish anything. The browser may display
remote source images by placing their existing URLs in ordinary `<img>` tags;
the browser then requests those URLs directly. Work offline if that is not
desired.

## Generate candidates

```bash
python -m deterministic_pipeline.review generate \
  --raw data/raw/auction_<ID>.json \
  --legacy viewer/src/data/auction_bundle.json \
  --reviewer "Bat" --per-stratum 2 \
  --output data/review/auction_<ID>_review.json
```

The optional legacy bundle adds disagreement context and is never treated as
truth. Selection is stable for the same inputs. It deduplicates strict products
and samples likely positives and near-negatives for every configured bucket,
plus unresolved products, disagreements, multi-labels, hard gates, and required
critical cases. The session records every selection reason and unavailable
strata. Generation leaves expected fields null and `reviewed` false.

Session output is restricted to `data/review/` inside the repository (or a
path outside it). Generation refuses existing files, directories, links,
source/reference/config paths, and the production bundle before reading the
auction. Omitting `--output` uses `data/review/review_session.json` and still
refuses collisions.

Two candidates per stratum is a practical first review, but will not usually
meet the evaluator's 20 positive and 20 negative examples per bucket. Increase
`--per-stratum` or review more auctions. Use rare-bucket exemptions only when
reviewed supply justifies them.

## Review locally

```bash
python -m deterministic_pipeline.review serve \
  --session data/review/auction_<ID>_review.json \
  --reviewer "Bat" --open
```

The server binds only to IPv4 loopback (`127.0.0.1` or `localhost`). Its local
dashboard has a searchable queue and a detail workspace with source text,
condition, category, structured gate fields, and image links. Filter by review
status, human-labelled bucket, condition, personal/critical status, or feedback
disposition. Selection-reason filtering becomes available only for records
whose context you explicitly revealed in that browser session. **Next unreviewed** and the queue keep
large sessions manageable.

Predictions and legacy labels are absent from the session response. **Reveal
for this item** requests machine context for that record alone; neither the
default response nor save responses expose it. Review the source before using
that control. The header watermark and amber context panel distinguish hidden
machine context from authoritative human labels.

For each controlled bucket, select **Expected**, **Forbidden**, or neither.
Then select a controlled subtype, expected provenance kinds, personal decision,
critical assertions, and a specific rationale. Check **Reviewed and complete**
only afterward. Save with Ctrl/Command+S; use N for the next unreviewed record
or Alt+up/down to move in the queue. The sticky status area reports saves,
validation errors, conflicts, and unsaved work. Closing, refreshing, or moving
records with unsaved changes prompts before discarding them. Saves use revision checks so a
stale tab cannot overwrite newer work, atomically replace the session, retain
a `.bak` recovery copy, and record actor, UTC time, and changed values. The
local server validates Host, Origin, JSON content type, and a session CSRF
token on mutations. Static assets have a restrictive content security policy;
listing text is rendered as text rather than HTML. This is an audit trail, not
cryptographic proof.

## Record improvement feedback

The **Owner feedback** panel is separate from gold truth. Use its controlled
disposition (`correct`, `rule miss`, `overmatch`, `taxonomy issue`, `source
insufficient`, or `revisit`) and reason, then optionally suggest buckets, a
seed, an exclusion, or a subtype. Feedback has its own optimistic revision and
audit trail. Saving it never changes expected/forbidden labels, classifier
rules, or evaluator exports.

**Download feedback JSON** creates a local, feedback-only artifact containing
source identifiers, typed suggestions, and feedback audit entries. It excludes
gold labels, machine predictions, and legacy labels. It is evidence for a
later, separately reviewed rules change; it has no import or publication path.

The readiness panel uses only completed human labels. It reports completion,
positive and near-negative coverage against static evaluator minimums, subtype
gaps, missing human critical assertions, and feedback counts. It does not expose
candidate selection strata or infer coverage from hidden predictions. These are
live diagnostics; the export command below remains the authoritative validation
gate.

Rare exemptions use this evaluator contract and must be written through the
local `/api/exemptions` endpoint so the session records their audit entry:

```json
{"Smart locks":{"reason":"Only three qualifying lots appeared across reviewed auctions.","min_positive":3,"min_negative":4}}
```

Reasons need at least 20 characters; minimums must be 1–19. Never lower a
threshold because the classifier currently fails it.

## Export and evaluate

```bash
python -m deterministic_pipeline.review export \
  --session data/review/auction_<ID>_review.json \
  --output data/review/deterministic_classification_gold.json \
  --reviewer "Bat" \
  --reviewed-on 2026-09-14 --attest-human-review
```

Export refuses unreviewed or incomplete items, validates controlled names,
duplicates, critical source semantics, and all coverage requirements before it
writes anything. The safe default output is under `data/review/`; it refuses
input/config/production paths, aliases, and other protected repository files.
An intentional `tests/fixtures/` export additionally requires
`--allow-test-fixture`. After coverage passes, it writes the evaluator contract
even when classifier accuracy fails because that failing gold set is needed to
tune the rules. Exit 0 means accuracy gates passed; exit 1 means the valid gold
was written but accuracy failed; exit 2 means invalid input or coverage. The
structured reviewer/date/checkbox attestation records process evidence and is
not cryptographic proof that a human performed the review.

Review artifacts under `data/review/` are ignored because they can contain
reviewer identity and source details. Do not commit bid/watch history. Commit
only a deliberately curated gold fixture in a separately reviewed change.
This workflow has no viewer build or publication command.
