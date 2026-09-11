You are estimating secondhand resale value for auction lots.

Attached is `{{INPUT_FILE}}`: a JSON array of {{N}} rows. Each row is one
distinct product; `lot_number` identifies it. See "Input fields" at the end
of this message for what each row contains.

For **every** row, return one object:

```json
{
  "lot_number": "S-4471",
  "est_resale_low": 40,
  "est_resale_high": 70,
  "resale_confidence": "medium",
  "resale_outlook": "good",
  "reasoning": "Comparable cordless drills in this condition sell for $40-70 on local marketplaces."
}
```

Rules:
- Each row is one **distinct product**, not one lot. `qty` says how many
  identical lots of it are in this auction. Value a single unit, but treat a
  high `qty` as local oversupply — 50 copies hitting one auction depresses
  what any one of them fetches. Mention it in the reasoning when it's high.
- Estimate what the item would realistically fetch **resold secondhand** in
  its stated condition — not its retail price. There is no retail figure in
  the input to anchor on: `title` and `condition` are the whole basis for the
  estimate.
- `est_resale_low` and `est_resale_high` are plain JSON numbers. No dollar
  signs, no commas, no quotes, no ranges written as text. A row needs at
  least one of the two to be usable.
- `resale_confidence` must be exactly `"low"`, `"medium"`, or `"high"` — how
  sure you are of the dollar range.
- `resale_outlook` must be exactly `"good"`, `"fair"`, or `"poor"` — how
  readily the item actually sells. These are independent: a used pair of
  shoes can be `"high"` confidence and `"poor"` outlook.
- `reasoning` is one short sentence. The key must be named `reasoning`.
- Use `model` to find the actual product before pricing it — a bare SKU
  title plus a model number usually identifies the item exactly, and pricing
  the wrong product is the main way this pass goes wrong.
- Discount for `damage`, `missing_parts`, `damaged`, `missing_major_parts`,
  and `functional` when present. An item that is damaged, non-functional, or
  missing major parts is usually worth parts value at most — say so in the
  reasoning. Also read `notes`: "20% USED" or "UNKNOWN AMOUNT REMAINING" on
  a consumable materially cuts what it fetches, and a lot whose notes say
  "DO NOT BID" is not a real item — value it at 0 and say why.
- **Value every row. Do not skip any.** Low-value, junk, damaged, and
  unidentifiable items still get a real numeric range — estimate low (even
  `0` to `5`) rather than omitting the row or returning `null`. A row that is
  missing, or has `null` for both bounds, is discarded by the build and those
  lots show no resale info at all.
- For obvious low-value lots keep `reasoning` to a short clause ("bulk
  plastic organizers, minimal secondhand demand"). Spend the detailed
  reasoning on lots where the number is actually arguable.
- `{{INPUT_FILE}}` contains {{N}} rows. Return exactly {{N}} objects, one per
  row, in the same order. The last row's `lot_number` is `{{LAST_LOT}}`. If
  you cannot complete all of them in one response, stop at a row boundary and
  tell me the last `lot_number` you finished so I can pick up from there —
  never silently drop rows to make the output fit.

Output:
- The result is one raw JSON array — no markdown fences, no preamble, no
  commentary before or after it.
- Return it as a downloadable file named exactly **`{{OUTPUT_FILE}}`** — not
  a generated or generic name. Only if you cannot produce a file, print the
  raw JSON array and nothing else, and I will save it under that name myself.

---

