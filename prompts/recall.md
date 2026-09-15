You are re-checking a short list of auction lots that an earlier pass over
this auction did **not** flag, but which look like they should have been.
The earlier pass judged lots for one specific person against a curated
interest list ("Bat's List"); this is its second look at its own likely
misses.

Two files are attached to this chat:
- `{{CONTEXT_FILE}}` — the config. Two files concatenated: `profile.yaml`
  describes what this household actually wants, and `buckets.yaml` defines
  the complete set of buckets, each with a `name`, a `description`, optional
  `examples`, and an optional `subtypes` vocabulary. Match lots
  **semantically against the `description`**.
- `{{INPUT_FILE}}` — the lots, as a JSON array of {{N}} rows. The last row's
  `lot_number` is `{{LAST_LOT}}`.

**Before you begin**, tell me how many buckets `{{CONTEXT_FILE}}` defines. It
should be {{N_BUCKETS}}. If you read a different number, or you cannot read
either file, stop there and say so — do not judge any lots.

Every row carries a `suspect` list: one or more buckets, each with a
`because` saying why this lot is suspected of belonging there. There are two
kinds of evidence:

- *"the pass flagged N lot(s) of "<title>" here"* — a product with the same
  leading title words **was** put in this bucket. Your question is whether
  this lot is the same kind of thing. Often it is: "PHYLOSAL A3 LED LIGHT
  PAD, ULTRA-THIN BOX" is the same tracing pad as "PHYLOSAL A3 LED LIGHT PAD
  FOR DIAMOND PAINTING". Often it is not: "10-IN-1 URINE TEST STRIPS" is not
  a "10-IN-1 STEAM MOP", and "DYSON SUPERSONIC" is a hair dryer whatever the
  vacuums next to it were.
- *"title contains "<word>" and the pass sent N% of this HiBid category
  here"* — a bucket's own keyword, in a category the bucket dominates. A toy
  vacuum, vacuum *storage* bags and a pool vacuum all contain "vacuum"; only
  a real vacuum belongs in "Vacuums & floor care".

**The evidence is a lead, not an instruction.** Judge each lot against the
bucket's `description` exactly as the first pass should have. A product line
or model name identifies an item as surely as a type word: "MX Keys" is a
keyboard and "Instax Mini film" is camera film whether or not the title says
so. A bucket whose description sets a quality bar still applies it in full.
You may also assign a bucket that is *not* in the `suspect` list if the lot
genuinely fits it, and you may assign more than one.

See "Input fields" at the end of this message for the other fields. Each row
is one distinct product; `qty` is how many identical lots it covers, and
your answer applies to all of them.

**Return only the lots you confirm.** A lot you do not name stays a
non-match. For each lot that DOES belong somewhere, return one object in
exactly the shape the first pass used:

```json
{
  "lot_number": "S-1a",
  "is_bats_list": true,
  "bats_buckets": ["Keyboards, keycaps & switches"],
  "bats_subtype": "mechanical keyboards",
  "personal_match": true,
  "personal_tags": ["pc_gaming"],
  "match_strength": "strong",
  "match_types": ["personal_use"],
  "personal_reasoning": "Enthusiast mechanical board for the desk setup in the profile."
}
```

Rules:
- `bats_buckets` values must be bucket `name` strings copied **exactly** from
  `buckets.yaml` — same spelling, casing, spacing, and punctuation. Never
  invent a bucket name.
- `is_bats_list` is `true` if and only if `bats_buckets` is non-empty.
- **`bats_subtype` is required whenever `is_bats_list` is true**: a 1-3 word
  lowercase label for what the item actually is, from the bucket's
  `subtypes` vocabulary when one fits.
- `personal_match` is a real JSON boolean and answers "does Bat want *this
  one*, now?" per `profile.yaml`. Be selective. Omit `personal_tags`,
  `match_strength`, `match_types`, and `personal_reasoning` entirely when it
  is `false`; when it is `true`, draw `personal_tags` from the `tags`
  vocabulary in `profile.yaml`, make `match_strength` one of `"strong"`,
  `"moderate"`, `"weak"`, and keep `personal_reasoning` to one sentence.
- Do **not** include `suspect`, `because`, `bats_category`, `category`,
  `subcategory`, `reasoning`, or `confidence` keys in your output.
- `{{INPUT_FILE}}` contains {{N}} rows. Read every one of them. When you have
  finished the last row, append this as the final element of the array,
  exactly: `{"chunk_complete": "{{LAST_LOT}}"}`. Never omit it, and never add
  it before you have actually read every row.

Output:
- The result is one raw JSON array — no markdown fences, no preamble, no
  commentary before or after it.
- Return it as a downloadable file named exactly **`{{OUTPUT_FILE}}`**. Only
  if you cannot produce a file, print the raw JSON array and nothing else,
  and I will save it under that name myself.

---
