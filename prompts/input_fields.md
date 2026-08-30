**Input fields.** Every lot has:
- `lot_number` — the join key. Copy it back verbatim, prefix included.
- `title` — usually the most informative field. Often a bare SKU or brand
  string rather than a sentence.
- `est_retail_price` — the auction house's retail reference, not a sale price.
- `condition` — the auction house's own grading, verbatim: one of
  Brand New - Sealed, Brand New - Open Box, New (Adjusted Quantity),
  Best Before (Grocery), Excellent, Good, New With Defects, Fair,
  Heavily Used, For Parts Only, Do Not Bid, or null. Note that
  **Brand New - Open Box is unused merchandise**, not used-in-great-shape —
  Excellent is the used grade. For Parts Only means non-functional, not
  merely worn. Best Before (Grocery) is new stock near its expiry date.
- `category` — HiBid's own category breadcrumb. **Frequently wrong** (a
  Lenovo Yoga laptop is filed under "Fitness & Exercise Equipment"). Use it
  as a weak hint only; trust `title` and `model` over it when they conflict.

These appear **only when the auction house recorded something**, so an
absent key is itself information — it means "nothing noteworthy":
- `model` — manufacturer model/SKU (~79% of lots). Often the only reliable
  way to identify what an item actually is when the title is a bare code.
- `size` — verified size; may be apparel sizing, a volume, or a colourway.
- `notes` — free-text caveats, e.g. "20% USED", "UNKNOWN AMOUNT REMAINING",
  "SEE PHOTOS". Occasionally "DO NOT BID" on lots that are not real items.
- `damage` / `missing_parts` — free-text detail on what is wrong.
- `damaged`, `missing_major_parts`, `functional` — flags present only when
  the answer is notable (`"Yes"`, `"Unknown"`, `"No"`, `"Unable to Test"`).
  **No `damaged` key means the item is not damaged.** Do not treat an absent
  flag as unknown or as a defect.
- `description` — free-form prose. Almost always absent for these listings.
