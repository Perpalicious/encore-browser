# ChatGPT Pass Prompts

The two ChatGPT passes referenced in `CLAUDE.md` step 4. Each returns one
JSON file.

| Pass | Input file | Save output as |
|---|---|---|
| 1. Bat's List + personal match | `auction_<ID>_candidates.json` | `auction_<ID>_flags.json` |
| 2. Resale valuation | `auction_<ID>_for_resale.json` | `auction_<ID>_resale_deduped.json` |

Pass 1 used to be two separate passes over the same 27k-row file — one for
bucket flags, one for personal match. They are now one pass, because they were
asking the same question ("does Bat care about this, and why?") of the same
rows, and splitting it doubled the output for nothing.

Pass 1 no longer reads every lot either. `tools/prefilter.py` shortlists
candidates per bucket and writes an all-false row for everything else, so the
model sees roughly a third of the auction, grouped by bucket. Pass 2 reads a
deduplicated file with one row per distinct product, since these auctions list
the same item dozens of times.

Every prompt below is written so its output matches exactly what `build/`
consumes. The "why this matters" notes under each prompt are the failure modes
that fail *silently* — the build won't crash, the data just quietly goes
missing.

---

## Input fields

Paste this block into each chat alongside the prompt. Both files share this
shape, and neither pass works well without knowing that an absent key is
meaningful. (Pass 2's rows carry one extra field, `qty`, described in its own
section. Pass 1's rows carry `cand` and sometimes `profile`, described in its.)

> **Input fields.** Every lot has:
> - `lot_number` — the join key. Copy it back verbatim, prefix included.
> - `title` — usually the most informative field. Often a bare SKU or brand
>   string rather than a sentence.
> - `est_retail_price` — the auction house's retail reference, not a sale price.
> - `condition` — the auction house's own grading, verbatim: one of
>   Brand New - Sealed, Brand New - Open Box, New (Adjusted Quantity),
>   Best Before (Grocery), Excellent, Good, New With Defects, Fair,
>   Heavily Used, For Parts Only, Do Not Bid, or null. Note that
>   **Brand New - Open Box is unused merchandise**, not used-in-great-shape —
>   Excellent is the used grade. For Parts Only means non-functional, not
>   merely worn. Best Before (Grocery) is new stock near its expiry date.
> - `category` — HiBid's own category breadcrumb. **Frequently wrong** (a
>   Lenovo Yoga laptop is filed under "Fitness & Exercise Equipment"). Use it
>   as a weak hint only; trust `title` and `model` over it when they conflict.
>
> These appear **only when the auction house recorded something**, so an
> absent key is itself information — it means "nothing noteworthy":
> - `model` — manufacturer model/SKU (~79% of lots). Often the only reliable
>   way to identify what an item actually is when the title is a bare code.
> - `size` — verified size; may be apparel sizing, a volume, or a colourway.
> - `notes` — free-text caveats, e.g. "20% USED", "UNKNOWN AMOUNT REMAINING",
>   "SEE PHOTOS". Occasionally "DO NOT BID" on lots that are not real items.
> - `damage` / `missing_parts` — free-text detail on what is wrong.
> - `damaged`, `missing_major_parts`, `functional` — flags present only when
>   the answer is notable (`"Yes"`, `"Unknown"`, `"No"`, `"Unable to Test"`).
>   **No `damaged` key means the item is not damaged.** Do not treat an absent
>   flag as unknown or as a defect.
> - `description` — free-form prose. Almost always absent for these listings.

---

## Shared rules (apply to both passes)

- **Output raw JSON only.** No ``` fences, no preamble, no "Here's your file",
  no trailing commentary. The verify step in `CLAUDE.md` rejects anything
  wrapped in markdown.
- **A top-level JSON array**, or an object with an `items` array. Nothing else.
- **`lot_number` is copied verbatim** from the input, including the `S-` /
  `M-` prefix on two-auction weeks. It is the only join key. A stripped or
  reformatted prefix means the row is orphaned and dropped.
- **Every pass must return a row for every row it was given** — no skipping,
  sampling, summarising, or stopping early. Each prompt below ends with a
  completeness instruction; keep it.
- **Replace `N` in that instruction with the real row count** before pasting.
  `tools/prefilter.py` and `tools/slim_resale.py` both print it. A concrete
  number is what makes the agent's own count checkable; leaving the literal
  `N` in makes the instruction unenforceable.
- **Truncation is the failure mode to watch.** A run that quietly stops early
  produces valid JSON that is simply short — indistinguishable from success by
  eye. Nothing in the build catches it; `tools/verify_passes.py` and
  `tools/expand_resale.py` do, by comparing lot sets rather than trusting the
  file. If a pass does come up short, they will say so and name the missing
  lots, and the fix is to re-run that pass for the missing rows and merge the
  results — never to hand-patch the file.

---

## Pass 1 — Bat's List + personal match (now FOUR passes: 1A-1D)

**Attach BOTH `buckets.yaml` and `profile.yaml` to every one of the four
chats.** Editing them in the repo does not update what a chat sees.
`tools/prefilter.py` prints the bucket count on every run; if a read-test in a
fresh chat reports a different number, the file didn't attach and that whole
pass will produce unusable bucket names.

### Why this is four prompts and not one

Two earlier shapes both failed, in opposite directions:

| shape | coverage | what went wrong |
|---|---|---|
| all ~27k lots, all buckets, one prompt (before 2026-08-16) | 100% | ~85% negative rate diluted it; narrow buckets starved. 77 lots had KEYBOARD in the title and **5** were flagged; storage bins scored **4 of 36**. Shipped 0% subtype coverage. |
| prefilter shortlist only (2026-08-16) | ~44% | reaches only **77.4%** of lots actually bid on, measured against three months of real bid/watch history. One pick in four could never be seen. |

Splitting by HiBid category fixes both at once: **every lot is judged exactly
once**, and each prompt carries 13-30 relevant buckets instead of 62. Coverage
goes to 100% while dilution goes down.

### The four passes

Run `python3 tools/split_passes.py <ID>` to produce the inputs. Defined in
`passes.yaml`; volumes below are from the week of 2026-08-16.

| pass | input file | covers | lots | focus buckets |
|---|---|---|---|---|
| **1A** | `auction_<ID>_pass_a.json` | Bed / Bath Items, Linens, Carpet — **all personal care lives here** | 6,595 | 13 |
| **1B** | `auction_<ID>_pass_b.json` | rest of Home Goods, Furniture, Business & Industrial | 7,770 | 30 |
| **1C** | `auction_<ID>_pass_c.json` | Construction & Farm, Lawn & Garden, Sporting Goods | 4,891 | 22 |
| **1D** | `auction_<ID>_pass_d.json` | Computers & Electronics, Kid & Baby, Toys, Fashion, tail | 7,767 | 17 |

Save each as: `data/categorized/auction_<ID>_flags_<a|b|c|d>.json`

Note the names. Step 5a chains all four onto `auction_<ID>_base.json` to produce
`auction_<ID>_categorized.json`. Saving any of them directly as
`_categorized.json` would drop every lot the other three passes cover.

**Each pass's rows are independent** — a pass returns exactly the rows it was
given, and nothing about another pass's lots. Never merge them by hand.

### Two things that are easy to get wrong

- **`focus_buckets` is advisory, not a filter.** `passes.yaml` names the
  buckets whose inventory actually sits in that pass, so the model knows where
  to look. It may still assign **any** bucket in `buckets.yaml`. HiBid's
  categories are noisy — a Barbie filed under Home Goods must still come back
  as `Barbies`, and 59% of Hand tools inventory sits under *Lawn & Garden*.
- **Pass 1A is the one to watch.** It is the densest slice and had almost no
  bucket coverage before 2026-08-30. If it returns near-zero flags, the
  personal-care buckets did not attach.

### Prompt

The prompt body now lives in **`prompts/flagging.md`**, not here. It moved
because `python -m classify` assembles it programmatically — substituting the
pass name and focus buckets, inlining the full `buckets.yaml` and
`profile.yaml`, and hashing the result into the run fingerprint. Extracting a
markdown blockquote out of explanatory prose to do that would have been
exactly the fragility `docs/PASS_SOURCES.md` warned about, so there is now one
copy of the text and this file keeps the rationale around it.

Two things changed in the move, both because the pass is now chunked:

- **Output shape.** A worker returns one object — `matches` (full rows) plus
  `no_match` (a plain array of `lot_number` strings) — rather than a row per
  lot. Negatives are still acknowledged individually, so *judged and rejected*
  stays distinguishable from *silently skipped*, but a rejection costs a lot
  number rather than four keys. `classify` expands `no_match` back into the
  four-key all-false rows before writing `_flags_<x>.json`, so the file on
  disk is shaped exactly as it always was.
- **Completeness.** Each worker is told its own chunk's row count and must
  account for every lot in it. The old "stop at a row boundary and tell me the
  last `lot_number`" escape hatch is gone: chunks are sized to be finishable,
  and a short chunk is retried and then bisected rather than resumed by hand.

The `cand` block is conditional. Pass files carry no `cand` or `profile` keys
— those come from `tools/prefilter.py`'s shortlist — so `classify/prompts.py`
includes that section only when the input actually has them, rather than
describing a field the worker cannot see.

To change what the flagging pass does, edit `prompts/flagging.md`. Doing so
changes the run fingerprint, which invalidates any chunks already ingested —
deliberately, so a taxonomy or wording change cannot half-apply to a week.


### Why this matters

- **Non-match rows need all four keys, not one.** Step 5a merges this file onto
  `_base.json` with `merge_categorized`, which replaces **whole rows** by
  `lot_number`. A returned `{"lot_number": "X", "is_bats_list": false}` would
  replace the base row and delete `bats_buckets` and `personal_match` with it,
  turning `personal_match` into `null` in the bundle and quietly changing step
  8's coverage count. `tools/verify_passes.py` checks the union of keys across
  all rows and catches this; the four-key rule prevents it.
- **A `bats_category` key silently changes how the file is parsed.**
  `build/transform.py` detects "Shape B" purely by that key's presence, and
  Shape B reads buckets from `bats_category`/`bats_subcategory` while
  **ignoring `bats_buckets` completely**. Same trap for naming the subtype
  `bats_subcategory`. Verify now fails on either.
- **Bucket names must match `buckets.yaml` exactly.** A near-miss name isn't
  corrected — it lands in the synthetic "Other" group, out of its real group in
  the viewer's nav. Verify now fails on unknown names rather than letting the
  build warn about them one step later.
- **`is_bats_list` must agree with `bats_buckets`.** A `true` with an empty
  array puts the lot on the Bat tab under no bucket, where
  `viewer/src/lib/filter.ts` renders it as an empty bucket view. Verify fails
  on the mismatch.
- **The subtype is what makes Bat's List navigable at the item level.** Without
  it a bucket like "Cleaning supplies & tools" is a flat list of 169 lots.
  `build/transform.py` lowercases and collapses whitespace so "Scrub Brushes"
  and "scrub  brushes" become one node, but it cannot merge genuine synonyms —
  which is why `buckets.yaml` now ships a `subtypes` vocabulary per bucket.
  The 2026-08-15 run emitted this field on **0 of 27,440 lots**, the old verify
  reported it and exited 0, and the third drill-down level was dead for a week.
  It is now a hard failure below 90% coverage of flagged lots.
- **The key is `personal_reasoning`, not `reasoning`.** `build/transform.py`
  reads `personal_reasoning` directly. This used to be renamed by a hand-written
  step in `CLAUDE.md`; that step is gone, so the pass must emit the final name.
  Verify fails if fewer than 95% of picks carry it.
- **Only literal `true` registers as a pick** (`viewer/src/lib/personal.ts`).
  The string `"true"` renders nothing and reports nothing.
- **`category`/`subcategory` from the agent are discarded** by `build/merge.py`
  — HiBid's own tree is the single source of truth for categorization.
- **`confidence` is deliberately not requested.** `build/transform.py` defaults
  it when absent, and nothing in the viewer ever reads it.
- **One bucket per lot is the known failure shape.** The 2026-08-15 run gave
  3,951 of 4,119 flagged lots exactly one bucket and only 168 two, against a
  prompt that said "list all that apply". The stated one-in-ten expectation
  above is there because the bare instruction demonstrably did not work. Step 8
  counts multi-bucket lots for exactly this reason.

---

## Pass 2 — Resale valuation

**Input file: `auction_<ID>_for_resale.json`** — not the same file as the other
two passes. It has one row per *distinct product* rather than per lot, because
these auctions list the same item many times over (58 identical lots is normal
here). It is typically 15-25% smaller.

Save as: `data/categorized/auction_<ID>_resale_deduped.json`

Note the `_deduped` suffix. `tools/expand_resale.py` reads that file and fans
each valuation back out to every lot in its group, producing the
`auction_<ID>_resale.json` the build actually consumes. Saving this pass's
output directly as `_resale.json` would leave most of the auction unvalued.

### Prompt

> You are estimating secondhand resale value for auction lots.
>
> I will give you auction lots as JSON. See "Input fields" below for what each
> lot contains. Each row is one distinct product; `lot_number` identifies it.
>
> For **every** row, return one object:
>
> ```json
> {
>   "lot_number": "S-4471",
>   "est_resale_low": 40,
>   "est_resale_high": 70,
>   "resale_confidence": "medium",
>   "resale_outlook": "good",
>   "reasoning": "Comparable cordless drills in this condition sell for $40-70 on local marketplaces."
> }
> ```
>
> Rules:
> - Each row is one **distinct product**, not one lot. `qty` says how many
>   identical lots of it are in this auction. Value a single unit, but treat a
>   high `qty` as local oversupply — 50 copies hitting one auction depresses
>   what any one of them fetches. Mention it in the reasoning when it's high.
> - Estimate what the item would realistically fetch **resold secondhand** in
>   its stated condition — not its retail price. Treat `est_retail_price` as a
>   ceiling reference, not the answer.
> - `est_resale_low` and `est_resale_high` are plain JSON numbers. No dollar
>   signs, no commas, no quotes, no ranges written as text. A row needs at
>   least one of the two to be usable.
> - `resale_confidence` must be exactly `"low"`, `"medium"`, or `"high"` — how
>   sure you are of the dollar range.
> - `resale_outlook` must be exactly `"good"`, `"fair"`, or `"poor"` — how
>   readily the item actually sells. These are independent: a used pair of
>   shoes can be `"high"` confidence and `"poor"` outlook.
> - `reasoning` is one short sentence. The key must be named `reasoning`.
> - Use `model` to find the actual product before pricing it — a bare SKU
>   title plus a model number usually identifies the item exactly, and pricing
>   the wrong product is the main way this pass goes wrong.
> - Discount for `damage`, `missing_parts`, `damaged`, `missing_major_parts`,
>   and `functional` when present. An item that is damaged, non-functional, or
>   missing major parts is usually worth parts value at most — say so in the
>   reasoning. Also read `notes`: "20% USED" or "UNKNOWN AMOUNT REMAINING" on
>   a consumable materially cuts what it fetches, and a lot whose notes say
>   "DO NOT BID" is not a real item — value it at 0 and say why.
> - **Value every row. Do not skip any.** Low-value, junk, damaged, and
>   unidentifiable items still get a real numeric range — estimate low (even
>   `0` to `5`) rather than omitting the row or returning `null`. A row that is
>   missing, or has `null` for both bounds, is discarded by the build and those
>   lots show no resale info at all.
> - For obvious low-value lots keep `reasoning` to a short clause ("bulk
>   plastic organizers, minimal secondhand demand"). Spend the detailed
>   reasoning on lots where the number is actually arguable.
> - Output a raw JSON array only — no markdown fences, no commentary.
> - The file contains N rows. Return exactly N objects, one per row, in the
>   same order. If you cannot complete all of them in one response, stop at a
>   row boundary and tell me the last `lot_number` you finished so I can pick
>   up from there — never silently drop rows to make the output fit.

### Why this matters

- **The key is `reasoning`, not `resale_reasoning`.** `build/resale.py:104`
  accepts either, and `tools/expand_resale.py` forwards `reasoning`, so a file
  using `resale_reasoning` loses the text on the way through.
- **Prices must parse as floats.** `"$40"` fails `float()` and is coerced to
  `None`; a row where both low and high end up `None` is dropped from the index
  entirely (`build/resale.py:95`), with no warning.
- **Enum values are normalized then nulled if unrecognized.** Anything outside
  the allowed sets becomes `None` silently, which drops the lot out of the
  viewer's resale filters.
- **The two enums drive a real filter.** The viewer's "potential resale" view
  requires outlook `good` or `fair` **and** confidence `medium` or `high`
  (`viewer/src/lib/resale.ts:46`). Grading everything `"low"` confidence
  empties that view.
- **Nothing enforces full coverage — you have to check it.** The resale join is
  lenient by design: an unvalued lot just keeps `None` and the build neither
  warns nor fails. So a pass that truncated at lot 8,000 produces a clean,
  successful build with two-thirds of the auction missing its resale data. The
  coverage check in `tools/expand_resale.py` and the "with resale" count in
  `CLAUDE.md` step 8 are what stand between a truncated run and a quietly wrong
  site.
---

Once both files are saved, tell Claude and it will pick up at
`CLAUDE.md` step 5.
