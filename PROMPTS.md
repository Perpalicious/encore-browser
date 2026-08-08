# ChatGPT Pass Prompts

The three ChatGPT passes referenced in `CLAUDE.md` step 4. Each returns one
JSON file.

| Pass | Input file | Save output as |
|---|---|---|
| 1. Bat's List flagging | `auction_<ID>_for_agent.json` | `auction_<ID>_categorized.json` |
| 2. Resale valuation | `auction_<ID>_for_resale.json` | `auction_<ID>_resale_deduped.json` |
| 3. Personal match | `auction_<ID>_for_agent.json` | `auction_<ID>_personal.json` |

Passes 1 and 3 read every lot. Pass 2 reads a deduplicated file with one row
per distinct product, since these auctions list the same item dozens of times.

Every prompt below is written so its output matches exactly what `build/`
consumes. The "why this matters" notes under each prompt are the failure modes
that fail *silently* — the build won't crash, the data just quietly goes
missing.

---

## Input fields

Paste this block into each of the three chats alongside the prompt. All three
files share this shape, and none of the passes work well without knowing that
an absent key is meaningful. (Pass 2's rows carry one extra field, `qty`,
described in its own section.)

> **Input fields.** Every lot has:
> - `lot_number` — the join key. Copy it back verbatim, prefix included.
> - `title` — usually the most informative field. Often a bare SKU or brand
>   string rather than a sentence.
> - `est_retail_price` — the auction house's retail reference, not a sale price.
> - `condition` — one of New, Like New, Good, Fair, Heavily Used, or null.
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

## Shared rules (apply to all three passes)

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
  `tools/slim.py` and `tools/slim_resale.py` both print it. A concrete number
  is what makes the agent's own count checkable; leaving the literal `N` in
  makes the instruction unenforceable.
- **Truncation is the failure mode to watch.** These are single-pass runs over
  tens of thousands of rows, and a run that quietly stops early produces valid
  JSON that is simply short — indistinguishable from success by eye. Nothing
  in the build catches it; `tools/verify_passes.py` and
  `tools/expand_resale.py` do, by comparing lot sets rather than trusting the
  file. If a pass does come up short, they will say so and name the missing
  lots, and the fix is to re-run that pass for the missing rows and merge the
  results — never to hand-patch the file.

---

## Pass 1 — Bat's List flagging

**Attach `buckets.yaml` to the chat.** Editing it in the repo does not update
what the chat sees. It currently has **45 buckets**; if a read-test in a fresh
chat reports a different number, the file didn't attach and the whole pass will
produce unusable bucket names.

Save as: `data/categorized/auction_<ID>_categorized.json`

### Prompt

> You are flagging auction lots against a curated interest list ("Bat's List").
>
> I have attached `buckets.yaml`. It defines the complete set of buckets. Each
> bucket has a `name`, a `description`, and optional `examples`. Match lots
> **semantically against the `description`** — `examples` are illustrative
> hints, not an exhaustive whitelist. A generic or off-brand item still matches
> if it fits the description. Before you begin, tell me how many buckets you
> read so I can confirm the file attached correctly.
>
> I will give you auction lots as JSON. See "Input fields" below for what each
> lot contains.
>
> For **every** lot I give you, return one object:
>
> ```json
> {
>   "lot_number": "S-1a",
>   "is_bats_list": true,
>   "bats_buckets": ["Power tools"],
>   "bats_subtype": "impact drivers"
> }
> ```
>
> Rules:
> - Return one row for **every** input lot, including lots that match nothing.
>   For those, set `is_bats_list` to `false` and `bats_buckets` to `[]`.
>   Never omit a lot, and never return only the matches.
> - `bats_buckets` values must be bucket `name` strings copied **exactly** from
>   `buckets.yaml` — same spelling, casing, spacing, and punctuation
>   (e.g. `"Garden & lawncare misc"`, not `"Garden and lawncare misc"`).
>   Never invent a bucket name.
> - A lot may match more than one bucket. List all that apply. `is_bats_list`
>   is `true` if and only if `bats_buckets` is non-empty.
> - `bats_subtype` is a free-form 1-3 word label describing **what the item
>   actually is**, one level finer than the bucket — `"scrub brushes"`,
>   `"detergents"` and `"mops & brooms"` inside `"Cleaning supplies & tools"`;
>   `"impact drivers"` and `"circular saws"` inside `"Power tools"`. Lowercase.
>   **Reuse the same wording across the whole run** rather than inventing a new
>   phrasing per lot — these become navigation, so `"scrub brushes"` on forty
>   lots is useful and forty near-synonyms are not. Omit the key (or use
>   `null`) whenever `is_bats_list` is `false`.
> - Use `model` to identify items whose title is a bare SKU or an ambiguous
>   brand word — it is often the difference between correctly bucketing a lot
>   and missing it. Do not let a wrong `category` talk you out of a match the
>   title and model clearly support.
> - Use these four keys and no others. In particular do **not** include a
>   `bats_category`, `bats_subcategory`, `category`, `subcategory`, or
>   `confidence` key.
> - Output a raw JSON array only — no markdown fences, no commentary.
> - The file contains N rows. Return exactly N objects, one per row, in the
>   same order. If you cannot complete all of them in one response, stop at a
>   row boundary and tell me the last `lot_number` you finished so I can pick
>   up from there — never silently drop rows to make the output fit.

### Why this matters

- **The categorized file decides which lots exist in the bundle.** `build/merge.py`
  iterates the categorized items and looks each one up in the raw scrape — it
  does not iterate the raw file. Any lot missing from this file is missing from
  the site entirely, flagged or not. This is why the pass must return all rows,
  not just matches.
- **A `bats_category` key silently changes how the file is parsed.**
  `build/transform.py:17` detects "Shape B" purely by that key's presence, and
  Shape B reads buckets from `bats_category`/`bats_subcategory` while
  **ignoring `bats_buckets` completely**. One stray key empties every bucket
  in the bundle without any error.
- **Bucket names must match `buckets.yaml` exactly.** Unrecognized names fall
  into the synthetic "Other" group and get reported in the build's "no group"
  warning — which `CLAUDE.md` step 7 says must come back empty.
- **`category`/`subcategory` from the agent are discarded** by
  `build/merge.py:138`; HiBid's native tree is the source of truth. Asking for
  them wastes tokens and output budget.
- **`bats_subtype` must not be named `bats_subcategory`.** The two read alike,
  but `build/transform.py:17` detects "Shape B" purely by the presence of
  `bats_category` — and Shape B reads buckets from
  `bats_category`/`bats_subcategory` while ignoring `bats_buckets` entirely.
  The subtype key is deliberately named differently so it can never trip that
  detection.
- **The subtype is what makes Bat's List navigable at the item level.** It is
  the same mechanism that makes pass 3's `personal_tags` feel better organised
  than the 45 fixed buckets: wording that fits the item, instead of a coarse
  bin. `build/transform.py` lowercases and collapses whitespace so
  "Scrub Brushes" and "scrub  brushes" become one node, but it cannot merge
  genuine synonyms — that is why the prompt insists on consistent wording.
  `tools/verify_passes.py` reports subtype coverage so a pass that ignored the
  instruction is visible before you build.
- **`confidence` is deliberately not requested.** The `Lot` schema still has a
  `confidence` field and `build/transform.py:188` defaults it to `"low"` when
  absent, but nothing in the viewer ever reads it — only `resale_confidence`
  (a different field, from pass 2) drives any UI. Emitting it on 26k rows costs
  output budget for a value nobody sees. If a future UI change starts showing
  it, add `"confidence": "low" | "medium" | "high"` back as a fourth key.

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

## Pass 3 — Personal match

Save as: `data/categorized/auction_<ID>_personal.json`

This pass depends on a personal taste profile that is **not stored in this
repo** — it lives in the ChatGPT agent's configuration. Keep the profile in the
agent's instructions (or paste it at the top of the chat) and leave the
placeholder below pointing at it.

### Prompt

> You are identifying auction lots that match a specific person's tastes,
> interests, and household needs.
>
> [PERSONAL PROFILE — keep this in the agent's saved instructions: hobbies,
> brands, sizes, rooms being furnished, projects underway, things explicitly
> not wanted, etc.]
>
> I will give you auction lots as JSON. See "Input fields" below for what each
> lot contains.
>
> For **every** lot, return one object:
>
> ```json
> {
>   "lot_number": "S-1a",
>   "personal_match": true,
>   "personal_tags": ["woodworking", "garage"],
>   "match_strength": "strong",
>   "match_types": ["hobby"],
>   "reasoning": "Bench chisels suit the woodworking projects in the profile."
> }
> ```
>
> Rules:
> - `personal_match` must be a real JSON boolean `true` — not the string
>   `"true"`, not `1`. Only `true` counts as a pick.
> - **Return a row for every lot. Do not skip any.** For a lot that does not
>   match, return just `{"lot_number": "...", "personal_match": false}` — omit
>   `personal_tags`, `match_strength`, `match_types`, and `reasoning` entirely
>   for non-matches. Those short rows are cheap and let me verify that the pass
>   actually covered the whole auction rather than quietly stopping early.
> - `match_strength` is a single word describing how strong the match is —
>   use `"strong"`, `"moderate"`, or `"weak"`. It is rendered directly into the
>   badge text as "Personal pick — {strength} match", so keep it lowercase and
>   to one word.
> - `personal_tags` and `match_types` are short arrays of plain strings, shown
>   as chips in the UI. Keep tags to 1-3 words each. Reuse consistent tag
>   wording across the whole run rather than inventing a new phrasing per lot.
> - `reasoning` is one short sentence explaining the match, and the key must be
>   named `reasoning`.
> - Check `size` before flagging apparel or footwear — a great item in the
>   wrong size is not a match. Check `damage`, `missing_parts`, and the
>   `damaged` / `missing_major_parts` / `functional` flags too: do not flag a
>   broken or incomplete item as a pick unless the profile specifically wants
>   it for parts or repair.
> - Be selective about which lots get `personal_match: true`. That list is
>   meant to be short enough to actually read — if thousands come back `true`,
>   the pass has failed. Being complete (a row per lot) and being selective
>   (few `true`s) are both required.
> - Output a raw JSON array only — no markdown fences, no commentary.
> - The file contains N rows. Return exactly N objects, one per row, in the
>   same order. If you cannot complete all of them in one response, stop at a
>   row boundary and tell me the last `lot_number` you finished so I can pick
>   up from there — never silently drop rows to make the output fit.

### Why this matters

- **The merge step reads `reasoning`** and stores it as `personal_reasoning`
  (`CLAUDE.md` step 6). Naming the key `personal_reasoning` in the file means
  the field arrives empty.
- **Only literal `true` registers.** `viewer/src/lib/personal.ts:12` gates on
  `personal_match === true`, so a string `"true"` renders as "not a pick" while
  still counting in the step 8 "carry personal_match" total — which is why that
  step also reports the `=== true` count separately.
- **`match_strength` is free-form and unvalidated**, so a typo won't fail the
  build — it just renders into the badge verbatim ("Personal pick — Strong
  match" vs "strong").

---

## After all three files are saved

Hand back to `CLAUDE.md` step 5, which expands the deduplicated resale file to
every lot and then runs `tools/verify_passes.py` over all three — checking field
names, duplicate lot_numbers, and that each file describes *this* week's
auction rather than a leftover from last week.
