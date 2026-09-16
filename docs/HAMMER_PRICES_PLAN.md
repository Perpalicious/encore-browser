# Hammer prices — implementation plan

**Status:** approved by Bat 2026-09-16, to be implemented on a branch by a
cloud Claude Code session, then verified and deployed locally. Nothing in
this plan is deployed yet.

**Read `CLAUDE.md` first.** It owns the pipeline. This document adds one
optional side-channel to it and changes nothing about the weekly run order.

---

## 1. Goal

Show, on lots that are repeat products, what the same product **actually
sold for** in previous Encore auctions:

> Sold 6× last week · median $14 · range $9–$22 · 3 unsold

with a tappable detail listing the same figures for each earlier week the
product appeared in.

This is a **display aid at bid time**. It does not change what gets flagged,
bucketed, or personally matched. It does not feed any ChatGPT pass. Keep it
that way.

### Non-goals (do not build these)

- Any change to what the flagging or resale passes see.
- Per-lot bid ladders or bidder usernames in the bundle. `bidHistory`
  exposes real usernames — never ship those.
- Live/updating prices for the current, still-open auction.
- Tracking `data/hammer/` in git (see §7 — default is gitignored; the
  decision to track is Bat's and is deferred).

---

## 2. Verified API facts (measured 2026-09-14, do not re-derive)

The scraper already talks to HiBid's GraphQL endpoint via `curl_cffi`
impersonating Chrome — see `scraper/client.py` and `scraper/AUTH_NOTES.md`.
Everything below works **anonymously**, with the same session the scraper
uses, on **closed** auctions back to at least May 2026 (auction 741675).

1. `lotSearch(...).pagedResults.results[].bidList` is a `[Decimal]` — the
   bid-increment ladder — and after close it **still starts at the next
   valid bid above the final price**. Therefore:

   ```
   final_price = bidList[0] - (bidList[1] - bidList[0])
   ```

   Verified against `bidHistory` on 25 random closed lots: 23 exact matches,
   0 mismatches, 2 zero-bid lots (see next point). Ladder increments are
   consistent within a lot, so the formula is safe.

2. **Zero-bid lots** have a ladder starting at the opening bid (typically
   `[1.0, 2.0, 3.0, ...]`), so the formula yields `0`. Treat `final <= 0`
   as **unsold**, never as "$0". Also treat `len(bidList) < 2` as unsold.

3. `lotState.highBid`, `lotState.bidCount`, `lotState.priceRealized` all
   return **0 on every lot after close**. Do not use them.

4. `bidHistory(input: "<lot id>") { bids { bid count username } }` is the
   authoritative per-lot ladder (`bids[0].bid` is the hammer). It costs one
   request **per lot** — 28,000 per auction — and carries usernames. Use it
   only in a test or a one-off spot check, never in the weekly path.

5. Adding `bidList` to the query costs **no extra requests**: the whole
   auction is ~56 pages of 500. A full pull is ~15 seconds.

6. HiBid's schema is introspection-disabled but leaks names via
   `"Did you mean ..."` errors. The `Lot` type has no richer text than the
   50-char `lead` — no hidden description to exploit.

---

## 3. Product identity (the join key)

`lot_number` and HiBid `id` are **both per-listing** and recycle week to
week (93.9% lot_number overlap measured). Never join on them across weeks.

Join on **(title, condition)**:

```python
key = (title.strip().upper(), (condition or "").strip().upper())
```

This is exactly the grouping `tools/slim_resale.py:group_key` uses (its
other fields are all empty since HiBid's 2026-08-30 change). Use the same
normalisation on both sides:

- **hammer side:** `title` = raw `lead`; `condition` = first element of
  `scraper.condition.parse_condition(description)`. Since 2026-09-13 the
  description *is* the bare grading (`"EXCELLENT"`), and `parse_condition`
  handles that form.
- **build side:** the merged lot's `title` and `condition` fields, which
  `scraper/parser.py` already produced with the same function.

Measured coverage on the 2026-09-13 week against the archive: **22.8%** of
lots match the previous week alone, **36.9%** match any of five archived
weeks. Expect roughly one lot in three to carry a hammer figure at launch.

Known collision: two different products sharing a 50-char title, and
truncated titles (1.1% are cut at exactly 50 chars). Accept it — this is a
display line, and condition-in-key absorbs most of it.

---

## 4. Architecture

Mirror the existing **optional resale join** exactly. `build/resale.py` and
the `--resale` flag in `build/__main__.py` are the template: absent flag →
every lot gets nulls, nothing breaks, viewer renders nothing.

```
tools/hammer.py <ID>            post-close pull -> data/hammer/<close_date>_<ID>.json
                                (one row per PRODUCT, aggregated)
build/hammer.py                 load every file in data/hammer/, index by key,
                                attach to lots  (mirror of build/resale.py)
python -m build ... --hammer data/hammer/     optional; default off
viewer                          compact line on the card, per-week table in LotDetail
```

**The pull runs in step 0 of the *following* week's run**, before the
sweep — the auction is guaranteed closed by then. No new ritual for Bat.

### 4.1 `tools/hammer.py`

```
python3 tools/hammer.py <ID> [--out data/hammer]
python3 tools/hammer.py backfill <ID> [<ID> ...]
```

- Reuse `scraper.client`. **Do not change `LOT_SEARCH_QUERY`** — the weekly
  raw file must stay byte-identical in shape, and `scraper/__main__.py`'s
  `first_seen` logic reads that file. Instead add an optional `query`
  parameter to `fetch_all_lots` / `_build_payload` (default = current
  behaviour) and pass a slimmer query from `hammer.py`:

  ```graphql
  results { id lotNumber lead description bidList }
  ```

  Plus `auction(id:) { eventName }` is already fetched by the client; a
  close date is available from `lotState { timeLeftTitle }` — include it in
  the slim query and parse the date with the existing
  `scraper.parser._parse_close_at`. Use the **latest** close time across
  lots as the file's `close_date`. If parsing fails, fall back to today.

- Refuse to run on an auction that is not closed: if any lot's
  `lotState.status` is not `CLOSED` (add `status` to the slim query), exit
  non-zero with a clear message. Pulling a live auction would record
  mid-week prices as hammers.

- Aggregate per product key. Output shape (JSON, one object):

  ```json
  {
    "auction_id": 774972,
    "auction_name": "...",
    "close_date": "2026-09-13",
    "pulled_at": "2026-09-16T03:12:00+00:00",
    "lots_seen": 28034,
    "products": [
      {
        "title": "SHARK HD430C FLEXSTYLE",
        "condition": "Excellent",
        "sold": 6,
        "unsold": 3,
        "median": 14.0,
        "low": 9.0,
        "high": 22.0,
        "prices": [9.0, 11.0, 13.0, 15.0, 18.0, 22.0]
      }
    ]
  }
  ```

  `prices` is the sorted list of **sold** finals only (kept so a later
  re-aggregation is possible); `median/low/high` are over `prices`;
  `unsold` counts lots with `final <= 0` or a short ladder. A product with
  `sold == 0` is still emitted (with `median/low/high = null`) — "listed 12×,
  sold 0" is information.

- Write atomically (temp file + `os.replace`). File name
  `<close_date>_<ID>.json`. Re-running overwrites the same file — safe.

- Never write to `data/raw/`. Never write to `data/categorized/`.

- Print a summary: lots seen, products, sold/unsold totals, top 5 products
  by `sold`, and the file path.

- `backfill` is the same thing in a loop with a 2-second pause between
  auctions. Known **closed** Encore auction IDs from this repo's history:

  ```
  741675 745313 749101 763293 764522 764523 764524 764528 764529 764530 764604 774972
  ```

  Some of these may be the Monday half of a two-auction week or a partial
  run; some may return 0 lots. Skip any that return 0 lots or are not
  CLOSED, and say so. **Do not include 776904** — it is the current week
  and still open.

### 4.2 `build/hammer.py`

Mirror `build/resale.py`: `load_hammer_files(dir) -> list`,
`build_hammer_index(files) -> dict[key, list[week]]`, `attach_hammer(lots,
index) -> int attached`.

- Read every `*.json` in the directory. Sort weeks by `close_date`
  **descending** so index 0 is most recent. **Recency wins**: the card
  shows week 0; the detail shows all weeks.
- Cap history at the **8 most recent weeks** per product.
- Skip a file that fails to parse; print a warning naming it; continue.

To keep the bundle small, **do not copy history onto every lot**. 58 lots
share one product. Instead:

- Add a top-level `hammer` map to the bundle keyed by a compact string key
  (`f"{title}|{condition}"` upper-cased) whose value is
  `{"weeks": [ {close_date, sold, unsold, median, low, high}, ... ]}`.
  Omit `prices`.
- Each lot gets `hammer_key: str | null`. Nothing else on the lot.

The bundle is already a dict with `lots` and `scrapes`; `hammer` sits next
to them. Measured: ~37% of lots match, dedup by product makes this a few
hundred KB raw and a few tens of KB gzipped.

### 4.3 `build/schema.py` and `build/__main__.py`

- `Lot` gains `hammer_key: Optional[str] = None`. Document it next to the
  resale fields with the same "None when the flag is absent" wording.
- `--hammer PATH` (a directory). Optional. When present, call
  `build/hammer.py`, print `hammer: N products across M weeks; K of L lots
  matched`. When absent, print nothing new.
- The fidelity report already prints resale coverage; add one line for
  hammer coverage in the same style.

### 4.4 Viewer

- `viewer/src/lib/types.ts`: `hammer_key: string | null` on `Lot`; a
  `HammerWeek` type and `hammer: Record<string, {weeks: HammerWeek[]}>` on
  the bundle type.
- `viewer/src/lib/hammer.ts`: `hammerFor(lot, bundle) -> weeks | null`,
  plus a formatter that yields the compact line. Format money with the
  existing `formatMoney` from `lib/resale.ts` — do not add a second money
  formatter.
- **Card (`LotCard.tsx`, `LotRow.tsx`)**: one compact line, greyscale, only
  when `weeks.length > 0`. Latest week only:

  `Sold 6× · med $14 · $9–$22 · 3 unsold`

  If `sold == 0`: `Listed 12× · none sold`.
  Truncate gracefully at narrow widths (drop the range first, then unsold).
- **Detail (`LotDetail.tsx`)**: a small table, one row per week, newest
  first: date · sold · unsold · median · range. This is the "tappable"
  history Bat asked for — the card is already the tap target that opens
  the detail, so no new gesture is needed.
- **`docs/design/README.md`** says money is *"The only money figure on a
  lot"* and the retail price was deliberately removed on 2026-09-10 because
  a second, weaker figure invited comparison. This line is a **stronger**
  figure than the resale estimate (real transactions vs a model's guess),
  and Bat approved it. Update that row of the README to say so explicitly,
  and keep the two visually distinct: resale stays where it is; the hammer
  line is smaller, mono, and reads as history, not a valuation.
- No new filter, no new sort, no new rail button. Display only.

---

## 5. Tests (required — the suite must stay green)

Python (`python3 -m pytest -q`, testpaths in `pyproject.toml`; add
`tools/tests/test_hammer.py` and `build/tests/test_hammer.py`):

- Final-price derivation: `[1450, 1475, 1500]` → 1425; `[1.0, 2.0, 3.0]` →
  unsold; `[]` and `[5.0]` → unsold; non-uniform ladder still uses the first
  two elements.
- Aggregation: median/low/high over sold only; unsold counted; `sold == 0`
  product still emitted with nulls.
- Refuses a non-CLOSED auction (mock the client; do not hit the network in
  tests).
- The slim query does not alter the scraper's default query (assert
  `LOT_SEARCH_QUERY` unchanged and `fetch_all_lots()` default payload
  unchanged).
- Build join: key normalisation matches `tools/slim_resale.group_key` for
  title+condition; recency ordering; 8-week cap; unparseable file skipped
  with a warning; absent `--hammer` leaves every `hammer_key` None and no
  `hammer` map in the bundle.
- Bundle shape: `hammer` map present iff flag given; keys referenced by
  lots all exist in the map.

Viewer (`cd viewer && npm test && npm run lint && npm run build`):

- Render tests for the card line (sold, unsold-only, absent) and the detail
  table (multi-week ordering). Follow the existing `*.render.test.tsx`
  pattern.

---

## 6. Live check (attempt it, but do not depend on it)

From a cloud sandbox HiBid may or may not clear Cloudflare (see
`scraper/AUTH_NOTES.md` — datacenter IPs were blocked before `curl_cffi`).
Try:

```bash
python3 tools/hammer.py 774972 --out /tmp/hammer
```

If it works, confirm `lots_seen` is 28,034 and spot-check that
`LOGITECH G915 X LIGHTSPEED KEYBOARD` or `ASUS TUF A18 LAPTOP` appear with
plausible prices (the laptop hammered at $1,425). If it returns 403, say so
in the PR and move on — Bat will run the backfill locally. **Do not commit
any pulled data.**

---

## 7. Storage and retention

- `data/hammer/` is **gitignored** (add the line next to `data/archive/`).
  Add a short paragraph to `CLAUDE.md`'s retention section: *keep
  `data/hammer/` indefinitely; it is ~1 MB per week and is the one thing in
  `data/` that becomes more useful with age.* Do **not** add it to the
  step-0 sweep.
- Add the pull to `CLAUDE.md` step 0 as the first line, before `git pull`
  is fine or immediately after — Bat's call, default after:

  ```bash
  python3 tools/hammer.py <LAST_WEEK_ID>     # last week is closed by now
  ```

  and to step 6 add `--hammer data/hammer/` to the build command with the
  same "optional; drop it and every lot keeps null" wording resale has.
- Open question, deliberately left for Bat: whether to track `data/hammer/`
  so a scheduled cloud job could do the Monday pull. Default no. Make the
  output directory a flag so flipping that later touches nothing else.

---

## 8. Things this branch must NOT do

- Do not merge, rebase onto, or cherry-pick from PRs #3–#6
  (`therealrozin`). They are under separate review. Branch from `main`.
- Do not modify `LOT_SEARCH_QUERY` or anything `scraper/__main__.py` writes.
- Do not write under `data/raw/` or `data/categorized/`.
- Do not deploy (`npx gh-pages`) and do not touch
  `viewer/src/data/auction_bundle.json`. Deploy is local by design.
- Do not add hammer figures to any prompt, chunk file, `context.yaml`, or
  resale input.
- Do not commit anything under `data/`.
- Do not add a filter, sort, or rail button for this.

---

## 9. Deliverable

A branch named `hammer-prices` pushed to `origin`, with:

- the code and tests above, suite green (`python3 -m pytest -q`; `cd viewer
  && npm test && npm run lint && npm run build`);
- `CLAUDE.md`, `docs/design/README.md`, and `.gitignore` edits from §4.4
  and §7;
- a PR description that states: what was verified live (or that Cloudflare
  blocked it), the test counts, and the exact commands Bat runs next:

  ```bash
  git fetch && git checkout hammer-prices
  python3 tools/hammer.py backfill 745313 749101 764523 764524 774972   # + others that are CLOSED
  python -m build ... --hammer data/hammer/ ...                          # step 6 with the flag
  # step 7 verify, then step 8 deploy
  ```

Bat's session will verify the branch on the real archive before anything is
merged or deployed.

---

## 10. Decisions already made (do not reopen)

| decision | answer | by |
|---|---|---|
| single number vs distribution | **median + range + counts** | Bat 2026-09-16 |
| unsold lots | **counted and shown**, never "$0" | Bat 2026-09-16 |
| multiple weeks | **recency wins on the card; full history in the detail** | Bat 2026-09-16 |
| join key | title + condition, same as `slim_resale.group_key` | measured |
| where the join lives | build, mirroring `--resale`; never the scraper | design |
| ships in bundle | product-keyed `hammer` map + `hammer_key` on lots | size |
| scope | display only; never touches flagging or resale passes | Bat, standing |
