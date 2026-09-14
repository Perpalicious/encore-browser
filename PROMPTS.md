# ChatGPT Pass Prompts

The two ChatGPT passes referenced in `CLAUDE.md` step 4. Each returns one
JSON file.

**The prompt text lives in `prompts/`, not here.** This file is the rationale:
what each pass is for, why it is shaped the way it is, and which mistakes fail
silently. The prompts themselves are templates —

| Pass | Template | Rendered per run as | Attach | Save reply as |
|---|---|---|---|---|
| 1. Bat's List + personal match | `prompts/flagging.md` | `auction_<ID>_chunk_NN_prompt.md` (one per chunk) | `context.yaml` + `auction_<ID>_chunk_NN.json` | `auction_<ID>_chunk_NN_flags.json` |
| 2. Resale valuation | `prompts/resale.md` | `auction_<ID>_resale_prompt.md` | `auction_<ID>_for_resale.json` only | `auction_<ID>_resale_deduped.json` |
| 1a. Recall repair (after pass 1) | `prompts/recall.md` | `auction_<ID>_recall_prompt.md` (one chat) | `context.yaml` + `auction_<ID>_recall.json` | `auction_<ID>_recall_flags.json` |

— and `tools/render_prompts.py` fills them in. `tools/chunk_flagging.py` and
`tools/slim_resale.py` both call it at the end of their run, so the rendered
files appear in `data/categorized/` next to the inputs they belong to. Each
rendered prompt is **complete and specific to one chat**: it names the file to
attach, the row count, the last `lot_number` for the `chunk_complete`
sentinel, the bucket count the read-test must report, and the exact name the
reply must be saved under. Paste the whole file; nothing in it needs editing.

Both templates end with `prompts/input_fields.md`, the shared description of
what each lot row contains. Edit a template to change a prompt — the next run
picks it up — and keep the `{{PLACEHOLDERS}}`: the renderer refuses to write a
prompt with one unfilled.

Pass 1 used to be two separate passes over the same 27k-row file — one for
bucket flags, one for personal match. They are now one pass, because they were
asking the same question ("does Bat care about this, and why?") of the same
rows, and splitting it doubled the output for nothing.

Neither pass reads every lot. Both run on one row per **distinct product** —
these auctions list the same item dozens of times, and the week of 2026-08-30
collapsed 25,195 lots to 19,250 products. `tools/chunk_flagging.py` and
`tools/slim_resale.py` build those inputs; `tools/expand_flags.py` and
`tools/expand_resale.py` fan the answers back out to every lot afterwards.

Pass 1 is additionally cut into numbered chunk files, because a pass over the
whole auction cannot finish in one response — see "Why pass 1 is chunked".

Every prompt is written so its output matches exactly what `build/`
consumes. The "why this matters" notes under each prompt are the failure modes
that fail *silently* — the build won't crash, the data just quietly goes
missing.

---

## Input fields

`prompts/input_fields.md` — appended to every rendered prompt. It says what
each lot row contains, which `condition` grades mean what (**Brand New - Open
Box is unused merchandise**; For Parts Only is non-functional), that
`category` is HiBid's and frequently wrong, and that an absent key means
"nothing noteworthy" rather than "unknown". Since 2026-08-30 HiBid renders
`model`, `size`, `notes` and the damage flags into an image, so in practice
`title` + `condition` carry the weight; the fields stay documented because the
scraper picks them up again by itself if that changes back.

Both passes' rows carry `qty` — how many identical lots the product appears
in — because both run on one row per distinct product.

---

## Shared rules (apply to both passes)

- **Output raw JSON only.** No ``` fences, no preamble, no "Here's your file",
  no trailing commentary. The verify step in `CLAUDE.md` rejects anything
  wrapped in markdown.
- **A top-level JSON array**, or an object with an `items` array. Nothing else.
- **`lot_number` is copied verbatim** from the input, including the `S-` /
  `M-` prefix on two-auction weeks. It is the only join key. A stripped or
  reformatted prefix means the row is orphaned and dropped.
- **Every pass must cover every row it was given** — no skipping, sampling,
  summarising, or stopping early. Each template ends with a completeness
  instruction; keep it. Pass 2 returns a row per input row. Pass 1 returns
  **matches only**, plus a terminal sentinel that proves it reached the end.
- **The row count and last `lot_number` in that instruction are real values,
  filled in by `tools/render_prompts.py`** from the input file on disk — not
  by the model reading the attachment, and not by hand. A concrete number is
  what makes the model's own count checkable, and the last lot is what
  `tools/expand_flags.py` compares the sentinel against. If the model
  supplied either itself, a run that read 2,000 of 2,750 rows could honestly
  report the last lot *it* saw and nothing would notice.
- **Every prompt names its own output file** (`auction_<ID>_chunk_03_flags.json`,
  `auction_<ID>_resale_deduped.json`). ChatGPT is asked to return a file under
  that name if it can; if it prints the JSON instead, save it under the name
  the prompt gives. `tools/expand_flags.py` reconciles each response against
  the chunk its number says it came from.
- **Truncation is the failure mode to watch.** A run that quietly stops early
  produces valid JSON that is simply short — indistinguishable from success by
  eye. Nothing in the build catches it; `tools/verify_passes.py` and
  `tools/expand_resale.py` do, by comparing lot sets rather than trusting the
  file. If a pass does come up short, they will say so and name the missing
  lots, and the fix is to re-run that pass for the missing rows and merge the
  results — never to hand-patch the file.

---

## Pass 1 — Bat's List + personal match (chunked)

**Attach `data/categorized/context.yaml` to every chat.** It is
`buckets.yaml` and `profile.yaml` concatenated by `tools/chunk_flagging.py`,
which prints the bucket count on every run. If a read-test in a fresh chat
reports a different number, the file did not attach and that chunk will produce
unusable bucket names.

### Why pass 1 is chunked

Three shapes have been tried. The first two failed in opposite directions:

| shape | coverage | what went wrong |
|---|---|---|
| all ~27k lots, all buckets, one prompt (before 2026-08-16) | 100% | ~85% negative rate diluted it; narrow buckets starved. 77 lots had KEYBOARD in the title and **5** were flagged; storage bins scored **4 of 36**. Shipped 0% subtype coverage. |
| prefilter shortlist only (2026-08-16) | ~44% | reaches only **77.4%** of lots actually bid on. Of 234 real bids, **94 (40%) match no seed at all** (`data/Watch/FINDINGS.md`) — one pick in four could never be seen. |
| dedup + chunk files (current) | 100% | — |

The current shape restores full coverage without the dilution, by cutting the
work two ways:

- **Dedup.** One row per distinct product, not per lot. Whether Bat wants a
  Revlon One-Step is one judgment, not the 129 separate lots it appeared in.
  25,195 lots became 19,250 products on 2026-08-30.
- **Chunk files.** A pass over the whole auction cannot finish in one
  response — the 2026-08-16 run returned 1.33 MB across 10,033 rows, roughly
  347K output tokens. It only completed because the old prompt invited the
  model to stop at a row boundary and report where it got to, which means the
  model chose every boundary and nothing verified them. A chunk is a real
  file, so a response can only name lots it was actually given.

### The chunks

Run `python3 tools/chunk_flagging.py <ID>`. It writes the chunk files, renders
one prompt per chunk, and prints a paste / attach / save checklist for every
chat. Typically **7 chunks plus `context.yaml` — 8 uploads.**

Products are ordered by category before cutting, so a chunk boundary falls
inside a category rather than at its edge and each chunk is mostly one kind of
thing. Every chunk gets the **identical prompt** and the **complete**
`buckets.yaml`; there is no per-chunk bucket list. Slicing the taxonomy per
chunk would destroy the cross-category catches this design exists to preserve —
a Barbie filed under Home Goods must still come back as `Barbies`, and 59% of
hand-tool inventory sits under *Lawn & Garden*.

Save each response as `data/categorized/auction_<ID>_chunk_NN_flags.json`,
matching the chunk number. Then `python3 tools/expand_flags.py <ID>`
reconciles them and writes `auction_<ID>_flags.json`.

### Two things that are easy to get wrong

- **Save the response under its own chunk number.** `expand_flags.py` checks
  each response against the chunk it belongs to, so a file saved under the
  wrong number fails as "lot_numbers not in this chunk" rather than merging
  silently.
- **Do not regenerate the chunks mid-run.** `tools/chunk_flagging.py` rewrites
  every chunk file and the group map. Responses already collected would then
  be reconciled against different chunks.

### Prompt

`prompts/flagging.md`, rendered once per chunk as
`data/categorized/auction_<ID>_chunk_NN_prompt.md`. Each rendering carries:

- the chunk file name and `context.yaml` as the two attachments
- the row count and last `lot_number`, both in the description of the input
  and again in the completeness rule with the `chunk_complete` sentinel
- the bucket count from `buckets.yaml`, so the opening read-test ("tell me
  how many buckets") has a stated right answer and the model is told to stop
  if it reads a different one — a missing attachment ends the chat before any
  lots are judged, instead of producing unusable bucket names
- the output name, `auction_<ID>_chunk_NN_flags.json`

Run one fresh chat per rendered prompt. Attach `context.yaml` and that
chunk's `.json`, paste the prompt whole, save the reply under the name it
gives.

### Why this matters

- **Omitted rows are how you tell a "no" apart from a skipped lot — as long as
  the sentinel is there.** The pass returns matches only, so a truncated
  response and a chunk with few matches look identical in the output. Two
  things separate them, and neither relies on the model reporting honestly:
  the chunk is a real file, so a response can only name lots it was given; and
  `{"chunk_complete": "<last lot_number>"}` must be the final element.
  Truncation removes the tail, so a missing or wrong sentinel *is* the
  truncation signal. `tools/expand_flags.py` checks both and writes nothing if
  either fails.
- **`expand_flags.py` writes the four-key row, the model does not.** Every
  product not named in a response is expanded locally to
  `{"lot_number": "...", "is_bats_list": false, "bats_buckets": [], "personal_match": false}`
  on every lot in its group. All four keys are load-bearing:
  `merge_categorized` replaces **whole rows** by `lot_number`, so a shorter row
  would delete `bats_buckets` and `personal_match` and turn `personal_match`
  into `null` in the bundle.
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

`prompts/resale.md`, rendered as
`data/categorized/auction_<ID>_resale_prompt.md` by `tools/slim_resale.py`.
It carries the input file name, the row count (stated twice: "contains N
rows" and "return exactly N objects"), the last `lot_number`, and the output
name `auction_<ID>_resale_deduped.json`. Attach `auction_<ID>_for_resale.json`
and nothing else — no `context.yaml`, no `buckets.yaml`, no `profile.yaml`.

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

Once every reply is saved under the name its prompt gave, tell Claude and it
will pick up at `CLAUDE.md` step 5.

## Pass 1a — recall repair (`prompts/recall.md`)

`tools/recall_check.py <ID> plan` runs after `expand_flags.py` and builds this
chat from the pass's own output. It exists because the flagging pass reads
type words far better than product names. Measured on 2026-09-13 (auction
774972): every Logitech lot whose title said KEYBOARD or MOUSE was flagged,
and none of the seven that said only "MX KEYS FOR MAC" or "MX ANYWHERE 3S MAC
COMPACT WIRELESS" — one of them between two flagged MX Keys rows in the same
chunk. Same run, larger: "PHYLOSAL A3 LED LIGHT PAD FOR DIAMOND PAINTING"
went to Kids' craft 44 times; the 64 lots of the identical pad titled
"ULTRA-THIN BOX" or "RECHARGEABLE LIGHT BOARD" went nowhere.

Both shapes are visible without a model: an unflagged product that shares
its leading title words with a flagged one, or that matches a bucket's own
seed inside a HiBid category the bucket dominates. Neither is proof — a toy
Dyson matches "vacuum" — so the suspects go to a chat that is asked a much
narrower question than the pass was: here is the lot, here is the flagged
sibling or the keyword that made it suspect, confirm or refuse against the
bucket description. That is a pairwise judgment the model does well; the
pass's task — spot one unrecognised row in 2,750 — is the one it does badly.

The output schema is identical to pass 1 and `apply` validates it with the
same code, so nothing downstream changes. The chat sees only products with
**no** bucket; adding a second bucket to something already flagged is a
different, smaller problem and would have the repair rewriting rows the pass
got right. What the check cannot see is a product with no flagged sibling and
no seed match — that residual is real and only a person noticing shrinks it.

The same 2026-09-13 run also motivated the "product line or model name"
rule now in `prompts/flagging.md`; the repair exists for whatever leaks past
it, and its per-bucket table is the measure of how much that is.
