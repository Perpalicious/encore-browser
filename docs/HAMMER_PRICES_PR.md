# PR: Hammer prices — what repeat products actually sold for

Implements `docs/HAMMER_PRICES_PLAN.md` in full. Branch: `hammer-prices`,
branched from `main` (`7b4480b`), no contact with PRs #3–#6.

Nothing is deployed. `viewer/src/data/auction_bundle.json` is untouched, so the
live site is unchanged until Bat runs the backfill and a build locally.

---

## What it does

A lot that is a repeat product now carries one compact line of real sale
history from past Encore auctions:

```
Sold 6× · med $14 · $9–$22 · 3 unsold
```

and the detail overlay lists the same figures per week, newest first. Display
only — no filter, no sort, no rail button, and it feeds no ChatGPT pass.

## What was verified live

**Nothing.** The live check in §6 could not run: this cloud sandbox's egress
proxy denies the host outright, so the request never reached HiBid.

```
$ python3 tools/hammer.py 774972 --out /tmp/hammer
anon POST attempt 1/5 raised ConnectionError: curl: (7) CONNECT tunnel failed, response 403
...
Failed auction 774972: All auth strategies failed …
$ echo $?
1
```

The proxy's own log names the denial: `connect_rejected — gateway answered 403
to CONNECT (policy denial or upstream failure), host
encoreauctions.hibid.com:443`. That is **not** the Cloudflare block
`scraper/AUTH_NOTES.md` warns about — the TLS handshake never happened, so
`curl_cffi`'s impersonation was never tested either way. The pull is unproven
against the real API and needs a local run.

What the failure did confirm is that it fails clean: non-zero exit, a clear
message naming the auction, and nothing written to the output directory.

So every number below about the API — the `bidList` formula, the 25-lot
`bidHistory` cross-check, 28,034 lots in auction 774972, the $1,425 laptop —
is the plan's, measured on 2026-09-14, not re-measured here.

## Test counts

| Suite | Before | After |
| --- | --- | --- |
| `python3 -m pytest -q` | 299 passed | **350 passed** (+51) |
| `cd viewer && npm test` | 157 passed | **182 passed** (+25) |
| `npm run lint` | clean | clean (`--max-warnings 0`) |
| `npm run build` | clean | clean (`tsc --noEmit` + `vite build`) |

New test files: `tools/tests/test_hammer.py`, `build/tests/test_hammer.py`,
`viewer/src/lib/hammer.test.ts`,
`viewer/src/components/HammerLine.render.test.tsx`. No network in any of them —
the one test that exercises the pull mocks `scraper.client.fetch_all_lots`.

The two that matter most:

- **The scraper's default query is byte-identical.** `test_default_payload_is_unchanged`
  asserts `_build_payload(741675, 2, 500)` still returns exactly the old dict,
  and `test_default_lot_search_query_shape` asserts `LOT_SEARCH_QUERY` still
  carries `featuredPicture`/`pictures`/`category` and still has no `bidList`.
  `data/raw/auction_<ID>.json`'s shape — which `scraper/__main__.py`'s
  `first_seen` carry-forward reads — cannot have moved.
- **Absent flag, absent feature.** `test_without_the_flag_there_is_no_hammer_map_and_no_keys`
  drives the real build CLI and asserts no `hammer` key in the bundle and every
  `hammer_key` null. An empty `data/hammer/` behaves identically.

## What changed

**New**

- `tools/hammer.py` — the post-close pull. `hammer.py <ID>` and
  `hammer.py backfill <ID> …`; `--out` defaults to `data/hammer/` and refuses
  to write anywhere under `data/raw/` or `data/categorized/`. Writes
  `<close_date>_<ID>.json` atomically (temp + `os.replace`), one row per
  product, with `prices` kept so a re-aggregation needs no re-pull.
- `build/hammer.py` — the join, mirroring `build/resale.py`. Reads every
  `*.json` in the directory, orders weeks by `close_date` descending, caps
  history at 8 weeks, skips an unreadable or wrong-shaped file with a warning,
  and ships only the product keys some lot actually references.
- `viewer/src/lib/hammer.ts` — lookup + the line formatter. Money goes through
  the existing `formatMoney` from `lib/resale.ts`; no second money formatter.

**Changed**

- `scraper/client.py` — `fetch_all_lots(auction_id, query=LOT_SEARCH_QUERY)`
  and `_build_payload(..., query=LOT_SEARCH_QUERY)`. Defaults unchanged;
  `LOT_SEARCH_QUERY` itself untouched. The GraphQL `operationName` is now read
  off the query document, so a caller's own query cannot get the two out of
  step.
- `build/schema.py`, `build/transform.py` — `hammer_key: Optional[str] = None`,
  documented and passed through beside the resale fields.
- `build/__main__.py` — `--hammer DIR` (optional), the join, a coverage line in
  the fidelity report, and `hammer` in the envelope only when non-empty.
- Viewer — `hammer_key` on `Lot`, `HammerWeek` and `hammer` on `Bundle`, the
  line on `LotCard`/`LotRow`, the table in `LotDetail`, plumbed from
  `App` → `LotGrid`.
- `CLAUDE.md` — the pull in step 0 (right after `git pull`), `--hammer` in step
  6 with the expected-coverage band, two lines in step 7's verify, and a
  retention paragraph.
- `docs/design/README.md` — the "only money figure on a lot" rule amended
  explicitly, per the plan.
- `.gitignore` — `data/hammer/`.

## Design decisions worth a look

**The card's height did not change.** The grid is virtualised off a uniform row
pitch (`useGridGeometry`), and the card's text block is a hard `TEXT_H`. A new
row would have meant making *every* card taller, including the ~two-thirds with
no history. So the line rides the existing meta row, right-aligned opposite the
bucket, and sheds detail as the column narrows: full at ≥230px, range dropped
at ≥170px (standard density is 196px), unsold dropped below that (compact is
150px). At 3-up and 4-up mobile, where the meta row is already dropped
entirely, the card shows no line and the detail overlay carries the history.

**It is not a second valuation.** Resale keeps its size, weight and `--text`
colour; the hammer line is 8.5–9.5px mono in `--dim3`. `docs/design/README.md`
is amended rather than quietly contradicted.

**Unsold is counted, never priced.** A lot nobody bid on has a ladder starting
at the opening bid, so the formula yields 0 — that is unsold. `sold == 0`
renders `Listed 12× · none sold`, and both the lib test and the render tests
assert no `$0` reaches the DOM.

**Only referenced keys ship.** 58 lots routinely share one product, and the
archive holds products that are not in this auction at all. Each lot carries a
`hammer_key` string; the history lives once in the bundle's `hammer` map.

## Known limits

- The join is exact on `(title, condition)`. 1.1% of `lead`s are truncated at
  exactly 50 chars, so two different products can collide; condition-in-key
  absorbs most of it. A title containing a literal `|` would also collide —
  accepted, and noted in `build/hammer.py`.
- Expect 20–40% coverage, not 100%. 0% *with files on disk* means the join
  broke, not that nothing repeated — the most likely cause is `condition`
  parsing as None everywhere, the failure `slim.py` already guards against.
- `tools/hammer.py` refuses an auction with any non-CLOSED lot. In `backfill`
  that is a skip with a message; for a single id it is a non-zero exit.

## What Bat runs next

```bash
git fetch && git checkout hammer-prices
pip install -e ".[dev]" --break-system-packages    # only if pytest is missing

# Confirm the suites are green locally too
python3 -m pytest -q
cd viewer && npm test && npm run lint && npm run build && cd ..

# The backfill. Skips anything not CLOSED or empty, and says which.
python3 tools/hammer.py backfill 745313 749101 764523 764524 774972
# or, for every id this repo has history for (776904 is deliberately excluded —
# it is the current week and still open):
python3 tools/hammer.py backfill

ls -la data/hammer/          # one file per auction that came back CLOSED

# Step 6 with the flag, then steps 7-8 as normal
python -m build --raw data/raw/auction_<ID>.json \
  --categorized data/categorized/auction_<ID>_categorized.json \
  --resale data/categorized/auction_<ID>_resale.json \
  --hammer data/hammer/ \
  --output viewer/src/data/auction_bundle.json --drop-orphans
```

Sanity checks before deploying:

- the build prints `Hammer: N products across M week(s); K/L lots matched` —
  K/L in the 20–40% band;
- step 7's verify prints a non-zero `carry a hammer_key` and a `hammer
  products` count well below it (products dedup lots — if they are equal,
  nothing deduped and something is wrong);
- spot-check a lot you remember from last week against what the card says.

If the backfill 403s locally too, that is the Cloudflare case
`scraper/AUTH_NOTES.md` describes and the fix is the same one the scraper
already uses — nothing in this branch changes the auth path.

Deploy (step 8, `npx gh-pages`) stays local and manual, as always.
