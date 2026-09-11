You are judging auction lots for one specific person, against a curated
interest list ("Bat's List").

Two files are attached to this chat:
- `{{CONTEXT_FILE}}` — the config. Two files concatenated: `profile.yaml`
  describes what this household actually wants (interests, projects underway,
  sizes, and things explicitly not wanted), and `buckets.yaml` defines the
  complete set of buckets, each with a `name`, a `description`, optional
  `examples`, and an optional `subtypes` vocabulary. **The buckets exist
  because of the profile**: they are the navigable expression of those
  interests. Match lots **semantically against the `description`** —
  `examples` are illustrative hints, not an exhaustive whitelist. A generic or
  off-brand item still matches if it fits the description.
- `{{INPUT_FILE}}` — the lots, as a JSON array of {{N}} rows. These are one
  chunk of a larger auction, already deduplicated to one row per distinct
  product. Judge only what you are given here. The last row's `lot_number` is
  `{{LAST_LOT}}`.

**Before you begin**, tell me how many buckets `{{CONTEXT_FILE}}` defines. It
should be {{N_BUCKETS}}. If you read a different number, or you cannot read
either file, stop there and say so — do not judge any lots.

See "Input fields" at the end of this message for what each lot contains.
Every bucket in `buckets.yaml` is available on every lot — the auction house's
own categories are unreliable, so a Barbie can be filed under Home Goods and
most hand tools are filed under Lawn & Garden. Trust the title over the
category.

Each row carries `qty`: how many identical lots this product appears in across
the auction. It is context, not a judgment — 129 copies of one item is a
saturated local market — and your answer applies to all of them.

**Return only the lots that match something.** Most will not, and a row
saying so costs more than it tells me. A product you do not name is recorded
as a judged non-match. For each lot that DOES match, return one object:

```json
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
```

Rules:
- A lot belongs in the output if `is_bats_list` is true **or**
  `personal_match` is true. A personal pick with no bucket of its own (pool
  upkeep, work lighting, vehicle fit) is returned with `bats_buckets: []` and
  `is_bats_list: false`. Everything else is omitted.
- `bats_buckets` values must be bucket `name` strings copied **exactly** from
  `buckets.yaml` — same spelling, casing, spacing, and punctuation (e.g.
  `"Garden & lawncare misc"`, not `"Garden and lawncare misc"`). Never invent
  a bucket name.
- `is_bats_list` is `true` if and only if `bats_buckets` is non-empty.
- **Assign every bucket that genuinely fits, not just the best one.** A
  gaming keyboard is both "Keyboards & PC peripherals" *and* "Electronics".
  Expect roughly one in ten flagged lots to carry two or more buckets.
  Assigning exactly one bucket to almost everything is a known failure mode
  of this task.
- **Reject freely.** A bucket whose description sets a quality bar ("do NOT
  flag generic no-brand pieces") applies that bar in full. Being complete
  about the lots you return and being selective about which ones qualify are
  both required.
- **`bats_subtype` is required whenever `is_bats_list` is true.** It is a
  1-3 word lowercase label for **what the item actually is**, one level finer
  than the bucket. Each bucket lists a `subtypes` vocabulary — use one of
  those verbatim when it fits, and invent a new 1-3 word lowercase label only
  when none does. **Reuse wording across the whole run**: these become
  navigation, so `"scrub brushes"` on forty lots is useful and forty near
  synonyms are not.
- `personal_match` must be a real JSON boolean `true` — not the string
  `"true"`, not `1`. Only `true` counts as a pick.
- A lot can be on Bat's List without being a personal pick, and vice versa.
  The bucket answers "is this a type Bat collects?"; the pick answers "does
  Bat want *this one*, now?" — which is where `profile.yaml`'s projects,
  sizes, and `not_wanted` list do their work.
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
- `condition` is the main quality signal available. **Brand New - Open Box is
  unused merchandise**, not used-in-great-shape; For Parts Only means
  non-functional. Do not make a broken item a personal pick unless the
  profile specifically wants it for parts or repair. Check `size` before
  flagging apparel or footwear — a great item in the wrong size is not a
  match.
- Be selective about `personal_match: true`. That list is meant to be short
  enough to actually read.
- Use these keys and no others. In particular do **not** include a
  `bats_category`, `bats_subcategory`, `category`, `subcategory`,
  `reasoning`, or `confidence` key.
- `{{INPUT_FILE}}` contains {{N}} rows. Read every one of them. When you have
  finished the last row, append this as the final element of the array,
  exactly: `{"chunk_complete": "{{LAST_LOT}}"}`. That is how I know you
  reached the end rather than stopping early — never omit it, and never add
  it before you have actually read every row. If you genuinely cannot finish
  in one response, say so in plain text instead of returning a partial array.

Output:
- The result is one raw JSON array — no markdown fences, no preamble, no
  commentary before or after it.
- Return it as a downloadable file named exactly **`{{OUTPUT_FILE}}`** — not
  a generated or generic name. Only if you cannot produce a file, print the
  raw JSON array and nothing else, and I will save it under that name myself.

---

