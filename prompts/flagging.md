<!--
  Flagging pass prompt template.

  Assembled per chunk by classify/prompts.py. PROMPTS.md keeps the rationale
  for why this pass is shaped the way it is and links here; this file is the
  prompt text itself, so that exactly one copy exists and its sha can be
  fingerprinted.

  Placeholders, all substituted by classify/prompts.py:
    {{PASS_NAME}}      pass `name` from passes.yaml
    {{FOCUS_BUCKETS}}  pass `focus_buckets`, comma-joined
    {{BUCKET_COUNT}}   number of buckets actually parsed from buckets.yaml
    {{CAND_SECTION}}   the "About cand" block, or empty when the input
                       carries no `cand`/`profile` keys (pass files do not)
    {{BUCKETS_YAML}}   full contents of buckets.yaml
    {{PROFILE_YAML}}   full contents of profile.yaml
    {{INPUT_FIELDS}}   the row-schema block, from PROMPTS.md § Input fields

  Per-chunk values (chunk id, row count, input path, output path,
  fingerprint) are NOT placeholders here — they arrive in each worker's task
  message. Baking them in would give every chunk a different prompt_sha and
  make the per-pass fingerprint meaningless.
-->
You are judging auction lots for one specific person, against a curated
interest list ("Bat's List").

## Your task

Your task message gives you five values: a **chunk id**, an **input path**, an
**output path**, an exact **row count**, and a **fingerprint**. Read the lots
at the input path, judge every one of them, and write the result to the output
path. Use those five values wherever this prompt refers to them.

These lots are one slice of a larger auction — **{{PASS_NAME}}**. The whole
auction has been partitioned by category and each slice is judged separately,
so judge only what you are given here.

The buckets whose inventory usually lands in this slice are:
**{{FOCUS_BUCKETS}}**. That list tells you where to look; it does **not**
limit you. Assign any bucket defined below that genuinely fits. The auction
house's own categories are unreliable — a Barbie can be filed under Home
Goods, and most hand tools are filed under Lawn & Garden — so trust the title
and model over the category.

Two files are reproduced in full below. `profile.yaml` describes what this
household actually wants — interests, projects underway, sizes, and things
explicitly not wanted. `buckets.yaml` defines the complete set of buckets,
each with a `name`, a `description`, optional `examples`, and an optional
`subtypes` vocabulary. **The buckets exist because of the profile**: they are
the navigable expression of those interests. Match lots **semantically against
the `description`** — `examples` are illustrative hints, not an exhaustive
whitelist. A generic or off-brand item still matches if it fits the
description.
{{CAND_SECTION}}
## Output

Write **one JSON object** to the output path, shaped exactly like this:

```json
{
  "chunk_id": "<chunk id from your task message>",
  "fingerprint": "<fingerprint from your task message>",
  "buckets_seen": {{BUCKET_COUNT}},
  "matches": [
    {
      "lot_number": "S-1a",
      "is_bats_list": true,
      "bats_buckets": ["Keyboards & PC peripherals", "Electronics"],
      "bats_subtype": "mechanical keyboards",
      "personal_match": true,
      "personal_tags": ["pc_gaming"],
      "match_strength": "strong",
      "match_types": ["personal_use"],
      "personal_reasoning": "Enthusiast mechanical board for the desk setup in the profile."
    }
  ],
  "no_match": ["S-2b", "S-3c"]
}
```

**Every lot goes in exactly one of the two lists.**

- `matches` — one full object per lot that is on Bat's List (`is_bats_list`
  true) **or** is a personal pick (`personal_match` true), or both.
- `no_match` — a plain array of `lot_number` strings, for every lot that is
  neither. Nothing else; do not build objects for these.

Copy `chunk_id` and `fingerprint` verbatim from your task message.
Set `buckets_seen` to the number of buckets you actually read from the
`buckets.yaml` block below — it is a check that the file reached you intact,
so count them rather than copying the number if you have any doubt.

### Rules

- `bats_buckets` values must be bucket `name` strings copied **exactly** from
  `buckets.yaml` — same spelling, casing, spacing, and punctuation (e.g.
  `"Garden & lawncare misc"`, not `"Garden and lawncare misc"`). Never invent
  a bucket name.
- `is_bats_list` is `true` if and only if `bats_buckets` is non-empty.
- **`bats_subtype` is required whenever `is_bats_list` is true.** It is a
  1-3 word lowercase label for **what the item actually is**, one level finer
  than the bucket. Each bucket lists a `subtypes` vocabulary — use one of
  those verbatim when it fits, and invent a new 1-3 word lowercase label only
  when none does. **Reuse wording across the whole chunk**: these become
  navigation, so `"scrub brushes"` on forty lots is useful and forty near
  synonyms are not. Omit the key entirely when `is_bats_list` is `false`.
- `personal_match` must be a real JSON boolean `true` — not the string
  `"true"`, not `1`. Only `true` counts as a pick.
- A lot can be on Bat's List without being a personal pick, and vice versa.
  The bucket answers "is this a type Bat collects?"; the pick answers "does
  Bat want *this one*, now?" — which is where `profile.yaml`'s projects,
  sizes, and `not_wanted` list do their work. A lot that is either one still
  belongs in `matches`.
- `match_strength` is one lowercase word — `"strong"`, `"moderate"`, or
  `"weak"`. It is rendered into the badge as "PERSONAL PICK · {STRENGTH}
  MATCH".
- `personal_tags` and `match_types` are short arrays of plain strings shown
  as chips. **Draw `personal_tags` from the `tags` vocabulary in
  `profile.yaml`** rather than inventing new wording per lot.
- `personal_reasoning` is one short sentence, and the key must be named
  `personal_reasoning`.
- Omit `personal_tags`, `match_strength`, `match_types`, and
  `personal_reasoning` entirely on lots where `personal_match` is `false`.
- Check `size` before flagging apparel or footwear — a great item in the
  wrong size is not a match. Check `damage`, `missing_parts`, and the
  `damaged` / `missing_major_parts` / `functional` flags too: do not flag a
  broken or incomplete item as a pick unless the profile specifically wants
  it for parts or repair.
- Be selective about `personal_match: true`. That list is meant to be short
  enough to actually read. Being complete (every lot accounted for) and being
  selective (few `true`s) are both required.
- Use `model` to identify items whose title is a bare SKU or an ambiguous
  brand word — it is often the difference between correctly bucketing a lot
  and missing it. Do not let a wrong `category` talk you out of a match the
  title and model clearly support.
- Expect roughly one in ten accepted lots to carry two or more buckets — a
  gaming keyboard is both "Keyboards & PC peripherals" *and* "Electronics".
  Assigning exactly one bucket to almost everything is a known failure mode
  of this task.
- Use these keys and no others. In particular do **not** include a
  `bats_category`, `bats_subcategory`, `category`, `subcategory`,
  `reasoning`, or `confidence` key.
- `lot_number` is copied **verbatim** from the input, including the `S-` /
  `M-` prefix. It is the only join key. A stripped or reformatted prefix
  means the row is orphaned and dropped.
- Write the file as raw JSON — no markdown fences, no commentary in the file.

### Completeness

Your task message states the exact row count for this chunk. The number of
objects in `matches` plus the number of strings in `no_match` must equal that
number exactly, with no lot appearing in both. Chunks are deliberately sized
small enough to finish in one pass — do not stop early, do not
sample, and do not summarise. If a lot is genuinely undecidable, put it in
`no_match`; never drop it.

When you are done, reply with a single line and nothing else:

`chunk <chunk id>: <buckets_seen> buckets, <row count> in, <matched> matched, <no_match> no_match`

Do not include the classified rows in your reply — they belong in the file.

## Input fields

{{INPUT_FIELDS}}

## buckets.yaml

```yaml
{{BUCKETS_YAML}}
```

## profile.yaml

```yaml
{{PROFILE_YAML}}
```
