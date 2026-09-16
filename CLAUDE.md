# Encore Lot Browser — Project Instructions

This repo scrapes weekly HiBid/Encore auctions, runs them through two
ChatGPT passes (combined Bat's List + personal match, and resale
valuation), builds a static bundle, and deploys it to GitHub Pages via a local
`gh-pages` branch push (NOT via GitHub Actions — the repo is capped on
Actions storage, so deploys must go through `npx gh-pages`, never `git
push` to trigger a workflow).

Machine paths: desktop (Grink) = `~/projects/encore-browser`, laptop
(Chickalettis) = `~/code/encore-browser`. Always confirm which machine
you're on and use the right path.

## When the user asks to run this week's auction

Ask for the auction ID(s) if not already given. Then follow this
sequence exactly. **Stop and wait for the user at the marked points —
the two ChatGPT passes cannot be run by you; they require the user to
paste the input file into a ChatGPT chat and paste the response back.**

### 0. Sync, pull last week's hammer prices, then sweep last week aside

```bash
git pull
python3 tools/hammer.py <LAST_WEEK_ID>     # last week is closed by now
```

The hammer pull is **optional and out-of-band** — it feeds no pass and no
build step by itself, and skipping it costs nothing this week. But it has to
happen *before* the sweep and *before* this week's scrape, because it can only
run on a CLOSED auction: it derives each lot's final price from the bid ladder
HiBid leaves behind, and refuses (non-zero, writing nothing) if any lot is
still open. Two-auction weeks: run it once per auction id. Output lands in
`data/hammer/<close_date>_<ID>.json`, one row per product; step 6 can then
join it onto this week's repeat products. See `tools/hammer.py`'s docstring
and `docs/HAMMER_PRICES_PLAN.md`.

Then move the previous week out of the way. This is not optional — last week's
`_categorized.json` and `_resale.json` sit at exactly the paths this week's
build reads, and lot numbers repeat across weeks (93.9% overlap measured), so
building against them succeeds and is wrong on nearly every lot:

```bash
mkdir -p data/archive/<LAST_RUN_DATE>
find data/categorized -maxdepth 1 -name 'auction_*.json' \
  ! -name 'auction_703264_categorized.json' \
  -exec mv -t data/archive/<LAST_RUN_DATE>/ {} +
rm -f data/categorized/context.yaml data/categorized/auction_*_prompt.md \
      data/raw/auction_*.json
```

`<LAST_RUN_DATE>` is the previous run's date (`ls data/archive/` shows what is
already there; the files' own mtimes show which week is currently in
`data/categorized/`). The `! -name` clause protects the tracked fixture
`auction_703264_categorized.json`, which `build/tests/` depends on; nothing
else in `data/categorized/` survives.

Match on `auction_*`, not `auction_combined_*`. A single-auction week writes
`auction_<ID>_*.json` under its own numeric ID, and the older `combined` glob
walked straight past those — leaving a full set of last week's files at exactly
the paths this week's build reads. See the retention section at the end for
what is safe to delete afterwards.

### 1. Scrape
```bash
python -m scraper --auction-id <ID> --output data/raw/auction_<ID>.json
```
If two auctions this week (Sun/Mon split), scrape both under their own
IDs before continuing.

### 2. Two-auction weeks only: prefix, then combine

Prefix lot_numbers so they never collide across the two auctions:
```bash
python3 -c "
import json
for auction_id, prefix in [('<SUNDAY_ID>', 'S'), ('<MONDAY_ID>', 'M')]:
    path = f'data/raw/auction_{auction_id}.json'
    d = json.load(open(path))
    is_dict = isinstance(d, dict)
    items = d.get('items', d) if is_dict else d
    for i in items:
        i['lot_number'] = f'{prefix}-{i[\"lot_number\"]}'
    if is_dict:
        d['items'] = items
    json.dump(d, open(path, 'w'))
    print(f'{auction_id}: prefixed {len(items)} lots with \"{prefix}-\"')
"
```

Combine into one raw file:
```bash
python3 -c "
import json
a = json.load(open('data/raw/auction_<SUNDAY_ID>.json'))
b = json.load(open('data/raw/auction_<MONDAY_ID>.json'))
items_a = a.get('items', a) if isinstance(a, dict) else a
items_b = b.get('items', b) if isinstance(b, dict) else b
combined = items_a + items_b
json.dump(combined, open('data/raw/auction_combined.json','w'))
print(f'{len(items_a)} + {len(items_b)} = {len(combined)} combined lots')
"
```

For the rest of this run, treat `<ID>` as `combined` on two-auction weeks.

Sanity check for zero collisions before continuing:
```bash
python3 -c "
import json
from collections import Counter
d = json.load(open('data/raw/auction_<ID>.json'))
items = d.get('items', d) if isinstance(d, dict) else d
dupes = [k for k,v in Counter(i['lot_number'] for i in items).items() if v>1]
print('duplicate lot_numbers:', len(dupes))
"
```
If non-zero, stop — something didn't get prefixed correctly.

### 3. Slim, then chunk (builds both passes' inputs)
```bash
python3 tools/slim.py <ID>
```
Writes `data/categorized/auction_<ID>_for_agent.json` and prints per-field
coverage. Sanity-check that printout before continuing:
- `lot_number`, `title`, `category`, `condition` must all be 100%
- `model`, `size`, `notes` and the damage flags are **0% and that is
  expected** — HiBid moved that detail into a per-lot report image during the
  week of 2026-08-30. `slim.py` prints a note saying so. Flagging runs on
  `title` + `condition` + `category`. If those fields ever come *back*, nothing
  needs changing; they flow through on their own.

`tools/slim.py` reparses `description_raw`, which is where that detail used to
live. Do not replace this step with a quick inline one-liner over
`description` — that field is empty on essentially every lot. See the docstring
in `tools/slim.py` for the full history, including how to recover the report
image if it is ever worth OCRing.

Then build the resale pass's smaller input (skip on a flagging-only week):
```bash
python3 tools/slim_resale.py <ID>
```
These auctions repeat the same product heavily (58 identical lots is normal),
so the resale pass values one representative per distinct product and the
result is fanned back out in step 5. Expect ~15-25% fewer rows. This is a
pure dedup, not a junk filter — every lot still ends up valued, and the
grouping key includes condition and damage so a sealed unit is never averaged
with a broken one. It also writes `auction_<ID>_resale_prompt.md`, the resale
chat's prompt with the row count, last lot and output name filled in.

Then build the flagging pass's chunks:
```bash
python3 tools/chunk_flagging.py <ID>
```
Dedups the auction to one row per distinct product, cuts it into numbered
chunk files, concatenates `buckets.yaml` + `profile.yaml` into a single
`data/categorized/context.yaml`, and renders one ready-to-paste prompt per
chunk (`auction_<ID>_chunk_NN_prompt.md`, via `tools/render_prompts.py` from
`prompts/flagging.md`). Check its printout:
- **the exact upload list** — normally 7 chunks plus `context.yaml`, 8 files
- the bucket count (72 as of 2026-09-15). Each rendered prompt states this
  number and tells the model to stop if its read-test disagrees, so a
  `context.yaml` that failed to attach ends the chat before any lots are judged
- dedup normally collapses 20-25% of lots (25,195 → 19,250 on 2026-08-30)
- the **paste / attach / save checklist** at the end — one entry per chat.
  Every per-chat value (row count, last `lot_number`, bucket count, output
  file name) is already inside the prompt file; nothing is substituted by hand

`--rows N` changes the chunk size; the default 2,750 is sized so one response
stays inside a single-response output ceiling. Do **not** re-run this
mid-pass — it rewrites every chunk file and the group map, and responses
already collected would then be reconciled against different chunks.

Why chunking exists: a pass over the whole auction cannot finish in one
response. The 2026-08-16 run returned 1.33 MB across 10,033 rows, roughly 347K
output tokens, and only completed because the prompt invited the model to stop
wherever it liked and report back — so the model chose every boundary and
nothing verified them. See the docstring in `tools/chunk_flagging.py`.

#### The prefilter is no longer in the flagging path

`tools/prefilter.py` still exists and is still worth running for its
diagnostics, but its shortlist **does not decide what the model sees any
more**. Before the 2026-08-30 taxonomy it reached only 77.4% of lots actually
bid on, with 40% of 234 real bids matching no seed at all; measured the same
way on the 2026-09-13 week it reaches 92% of bids, and the ungated pass 96%
(`data/Watch/FINDINGS.md`). Since 2026-08-30 it is
also matching on `title` + `category` alone, because the fields it used to read
are gone.

It is still the cheap way to measure seed quality, and `_base.json` is still
what step 5 merges onto:
```bash
python3 tools/prefilter.py <ID>
```

Measure recall before trusting a seed edit — this costs nothing and needs no
ChatGPT run. **The backtest replays seeds over the week the labels came from,
so it needs that week's slimmed file — NOT this week's `<ID>`:**
```bash
cp data/archive/<LAST_RUN_DATE>/auction_combined_for_agent.json \
   data/categorized/auction_bt_for_agent.json
python3 tools/prefilter.py bt --backtest data/archive/<LAST_RUN_DATE>/auction_combined_categorized.json
rm data/categorized/auction_bt_for_agent.json
```
Passing this week's `<ID>` instead joins last week's labels onto this week's
products — lot_numbers are recycled, so ~80-94% still "match" while pointing at
entirely different lots. Measured 2026-08-16 on identical seeds: **33.4%
cross-week vs 98.0% correctly paired.** The tool aborts on this rather than
printing the bogus table.

Treat the per-bucket table as a lead, not a verdict: it scores seeds against
labels that were themselves produced from the shortlist, so it cannot see what
the shortlist never showed the model. The bid history can.

### 4. STOP — hand off to the user

Tell the user: *"Everything is rendered — `tools/chunk_flagging.py` printed
the paste / attach / save checklist. One fresh ChatGPT chat per prompt:

- paste the whole of `data/categorized/auction_<ID>_chunk_NN_prompt.md`
- attach `data/categorized/context.yaml` **and** `auction_<ID>_chunk_NN.json`
- save the reply as `auction_<ID>_chunk_NN_flags.json` — the prompt says
  which name; ChatGPT will name the file itself if it returns one

...for each chunk. The prompt already contains that chunk's row count, last
`lot_number`, the bucket count (72) and its output name, so nothing in it
needs editing. Let me know when they're saved and I'll continue."*

If in doubt, `python3 tools/render_prompts.py <ID>` re-prints the checklist
and re-renders the prompts from the chunk files on disk without touching them
— it is safe mid-pass, unlike `chunk_flagging.py`.

The names matter. Each response must be saved under **its own chunk number**;
`tools/expand_flags.py` checks every response against the chunk it belongs to,
so a file saved under the wrong number fails rather than merging silently.

The pass returns **matches only** and must end with
`{"chunk_complete": "<last lot_number>"}`. That sentinel is the truncation
detector — a response that stops early loses its tail, so a missing or wrong
sentinel is caught in step 5.

If the week also needs resale, the same checklist ends with the resale chat:
paste `auction_<ID>_resale_prompt.md`, attach `auction_<ID>_for_resale.json`
with **no** config files (`docs/PASS_SOURCES.md`: the resale pass has no
notion of buckets), save as `auction_<ID>_resale_deduped.json`.

Do not proceed past this point until the user confirms the files exist.

### 5. Reconcile the chunks, assemble, expand resale, then verify

First reconcile every chunk response and fan the answers out to all lots:
```bash
python3 tools/expand_flags.py <ID>
```
Reads every `_chunk_NN_flags.json` against the `_chunk_NN.json` it belongs to
and writes `auction_<ID>_flags.json` with a row for **every** lot. It exits
non-zero and **writes nothing** on any of: a missing response file, a response
that is not valid JSON, a missing or wrong `chunk_complete` sentinel
(= truncation), a `lot_number` that was not in that chunk, a lot judged twice,
a forbidden key, or `is_bats_list` disagreeing with `bats_buckets`.

If it fails, report exactly which chunks it named and have the user re-run
those chats. Do not hand-patch the file — a partial `_flags.json` builds
cleanly and is quietly missing its flags.

#### 5a. Recall repair — one more chat, then STOP again

The pass reads type words well and product names badly: on 2026-09-13 it
flagged every Logitech lot whose title said KEYBOARD or MOUSE and none of the
ones that said only "MX KEYS FOR MAC", and it put "PHYLOSAL A3 LED LIGHT PAD
FOR DIAMOND PAINTING" in Kids' craft 44 times while leaving 64 lots of the
same pad titled "ULTRA-THIN BOX" unflagged. Those misses are detectable from
the run's own answers, so find them and re-judge only those:
```bash
python3 tools/recall_check.py <ID> plan
```
It lists every unflagged product that either shares its leading title words
with a product the pass DID flag, or matches a bucket's seed inside a HiBid
category that bucket dominates this week — normally 400-500 products, under
a fifth of one chunk — prints a per-bucket table, and writes
`auction_<ID>_recall.json` plus its rendered prompt. Then hand off:

*"One more chat: paste `auction_<ID>_recall_prompt.md`, attach
`context.yaml` **and** `auction_<ID>_recall.json`, save the reply as
`auction_<ID>_recall_flags.json`."*

Wait for the user, then fold the confirmations in:
```bash
python3 tools/recall_check.py <ID> apply
```
It validates the response exactly as `expand_flags.py` does (sentinel,
foreign lot_numbers, forbidden keys), refuses to run twice, keeps the
original as `_flags_before_recall.json`, and rewrites `_flags.json` in place
— so everything from here on is unchanged. Report how many suspects it
confirmed versus refused; a run that confirms nearly all of them means the
main pass regressed, not that the check is generous.

If the user wants to skip the chat this week, that is fine: `_flags.json` is
already complete without it. Never skip `plan` — its table is the cheapest
recall measurement there is.

Then merge onto the all-false base so the `lot_set_sha` is carried through:
```bash
python -m merge_categorized --existing data/categorized/auction_<ID>_base.json \
  --new data/categorized/auction_<ID>_flags.json \
  --output data/categorized/auction_<ID>_categorized.json
```
This reports `Merged <n_added> new items` — **`n_added` must be 0.** Anything
else means a `lot_number` that isn't in this week's auction, which is either a
hallucinated row or a stale file. Stop and investigate.

On a week that also ran resale, fan each valuation back out:
```bash
python3 tools/expand_resale.py <ID>
```
This reads `_resale_deduped.json` plus the group map from step 3 and writes
`auction_<ID>_resale.json`. It exits non-zero and writes nothing if any
product went unvalued — the signature of a truncated ChatGPT run.

Now verify:
```bash
python3 tools/verify_passes.py <ID>          # add --no-resale on a flagging-only week
```
This checks required fields, duplicate lot_numbers, and that each file's
lot_numbers match **this week's** slimmed file. That last check is the one
that matters: two-auction weeks all write to `auction_combined_*.json`, and a
previous week's file overlaps ~94% of this week's lot numbers, so a stale file
builds cleanly into a completely wrong bundle. Row counts alone will not catch
it; the `lot_set_sha` comparison catches it exactly.

It **fails** (not just reports) on: `bats_subtype` coverage under 90% of
flagged lots, bucket names absent from `buckets.yaml`, any `bats_category` key,
`is_bats_list` disagreeing with `bats_buckets`, and `personal_reasoning`
missing from more than 5% of picks. Each of those produces a clean-looking
build with wrong or missing data; the 0%-subtype run of 2026-08-15 shipped
precisely because this script reported and exited 0.

It also prints a per-bucket `shown / kept / rate` table. Those columns are
scored against `tools/prefilter.py`'s shortlist, which no longer decides what
the model sees — so read them as a comparison between the two, not as a
verdict on the pass. One shape is still worth reporting:
- **a bucket shown ≥20 candidates and keeping none** — the pass refused a
  bucket the seeds thought was well stocked, which is the exact failure this
  pipeline exists to fix

The `outside` column counts buckets assigned outside the shortlist. With the
prefilter out of the flagging path this number should now be *large*; it is a
measure of the shortlist's recall gap, not of the pass's accuracy. Mine it for
new seeds with
`python3 tools/prefilter.py <ID> --audit data/categorized/auction_<ID>_flags.json`.

If verify fails, report exactly what it said to the user and stop. Do not
proceed with a malformed, stale, or markdown-wrapped file.

### 6. Build the bundle
```bash
python -m build --raw data/raw/auction_<ID>.json \
  --categorized data/categorized/auction_<ID>_categorized.json \
  --resale data/categorized/auction_<ID>_resale.json \
  --hammer data/hammer/ \
  --output viewer/src/data/auction_bundle.json --drop-orphans
```
Drop the `--resale` line on a flagging-only week; the build treats resale as
optional and every lot simply keeps a null valuation. `--hammer` is optional
the same way — drop it and every lot keeps a null `hammer_key` with no sale
history shown. Unlike resale it is a *directory*, and it is cumulative: every
file `tools/hammer.py` has ever written is read, newest week first.

Check the build's own output for:
- `category_path` coverage ~100%
- resale coverage ~matches total lot count (or 0 on a flagging-only week)
- hammer coverage in the 20-40% band when `--hammer` was passed. That is
  normal, not a failure — about a third of lots are repeat products (32.8%
  measured). **0% with hammer files on disk** means the join broke, not that
  nothing repeated; it matches on title + condition, so a `condition` that
  parsed as None everywhere (see the `slim.py` gotcha below) zeroes it
- **the "no group" warning is EMPTY** — if it lists bucket names, those
  don't match `buckets.yaml` exactly and will fall into "Other"; report
  this to the user rather than silently continuing.

### 7. Verify the bundle (non-negotiable — this is the step that catches
silent data loss; do not skip it)
```bash
python3 -c "
import json
b = json.load(open('viewer/src/data/auction_bundle.json'))
lots = b['lots'] if isinstance(b, dict) else b
print(len(lots), 'lots')
print(sum(1 for l in lots if l.get('est_resale_low') is not None), 'with resale')
print(sum(1 for l in lots if l.get('personal_match') is not None), 'carry personal_match')
print(sum(1 for l in lots if l.get('personal_match') is True), 'are personal_match=true')
print(sum(1 for l in lots if l.get('bat_subtype')), 'carry a bat_subtype')
print(sum(1 for l in lots if len(l.get('bat_buckets') or []) >= 2), 'have 2+ buckets')
print(sum(1 for l in lots if l.get('hammer_key')), 'carry a hammer_key')
print('hammer products:', len((b.get('hammer') or {}) if isinstance(b, dict) else {}))
print('scrapes:', b.get('scrapes') if isinstance(b, dict) else None)
"
```
Report these numbers to the user. If resale or personal_match coverage
is 0 or unexpectedly low, STOP and investigate — do not deploy. Likely
causes: a filename mismatch between what was merged/built and what's on
disk, or a `--categorized`/`--resale` flag pointing at a stale file.

The last two lines are the regression check on the flagging pass itself.
Baseline before the prefilter (2026-08-15): **0** lots carried a subtype and
**168 of 4,119** flagged lots had two or more buckets. If `bat_subtype` is
near zero, the pass ignored the field again. If multi-bucket lots are near
zero, it collapsed back to picking one bucket per lot and the narrow buckets
are starving again — report both to the user rather than deploying past them.

### 8. Deploy
```bash
cd viewer && npm run build && npx gh-pages -d dist -b gh-pages && cd ..
```
`npm run build` MUST run after step 6 (bundle regeneration) — if a stale
`dist` exists from an earlier build, this step must rebuild it fresh, or
the deploy will ship old data. Never run `npx gh-pages` without a fresh
`npm run build` immediately before it in the same sequence.

Tell the user the deploy is live at
`https://perpalicious.github.io/encore-browser/` and suggest they hard
refresh (Ctrl+Shift+R) or check in an incognito window if the CDN is
slow to update (can take 1-3 minutes).

### 9. Commit and push to `main` (backs up code + data; does NOT trigger
a deploy — deploy already happened in step 8 via `gh-pages`)
```bash
git add -A
git commit -m "Update bundle: auction <ID>"
git push
```
If push is rejected ("fetch first"), run `git pull --no-rebase` then
`git push` again. If there's a conflict specifically on
`auction_bundle.json`, do NOT attempt to hand-resolve the JSON diff —
stop and ask the user; the correct resolution is almost always to keep
the locally just-built version.

## Mid-week delta (new lots after the weekly run)

The auction keeps growing after Sunday (Tue ~12k lots, Thu +6k, Fri +…). The
build is strict — a raw lot with no categorized row is dropped — so new lots
reach the viewer only after they have been judged. `tools/delta.py` runs the
normal pass on **just the new lots** and folds the answers into the week's
files without disturbing anything already judged. Preconditions: the week is
fully deployed (steps 1-9 done, `auction_<ID>_categorized.json` exists).

1. **Re-scrape** with the same command as step 1 — both auctions on a
   two-auction week, then re-run step 2's prefix + combine exactly as written.
   The scraper stamps every lot with `first_seen` (the run that first saw it,
   matched on HiBid's item `id`, so the prefixing does not break it); the
   build turns those into the numbered scrapes the viewer's SCRAPE filter
   shows. Two auctions scraped minutes apart count as one scrape.
2. `python3 tools/delta.py <ID> start` — writes
   `data/raw/auction_<ID>_dN.json` holding only the unjudged lots (not in the
   categorized file, not in an earlier unmerged delta) and prints the exact
   commands for the delta ID `<ID>_dN`. It refuses if nothing is new or if
   the raw carries no `first_seen` (an old scraper wrote it).
3. Run the printed commands: `slim.py`, `slim_resale.py`, `chunk_flagging.py`
   under `<ID>_dN`, the ChatGPT chats (STOP and hand off exactly as in step
   4), then `expand_flags.py`, `recall_check.py plan`/`apply`,
   `expand_resale.py`, all under `<ID>_dN`. Chunking under the delta ID is
   safe — its files are `auction_<ID>_dN_*` and never touch the parent's. The
   never-re-run rule still applies to `chunk_flagging.py <ID>`. Note the
   delta's chunking regenerates the shared `context.yaml`, and `slim.py`'s
   ≥50 % `condition` gate can trip on a tiny delta — that is a real signal
   about the new lots, not a tool bug.
4. `python3 tools/delta.py <ID> merge` — re-runs `slim.py <ID>` and
   `prefilter.py <ID>` on the full raw (fresh `_for_agent`, `_base`,
   `_prefilter` with the new `lot_set_sha`), then folds the week's
   `_categorized.json` and every `_dN_flags.json` onto that base, and the
   delta valuations into `_resale.json`. Lots pulled from the auction since
   the last scrape are reported as dropped; after that every fold must add
   0 rows — anything else is fatal. Re-running `merge` is safe.
5. Continue with steps 5 (verify), 6, 7 (expect one more entry under
   `scrapes:`), 8 and 9. Commit as `Update bundle: auction <ID> (delta dN)`.

Step 0's sweep already removes `_dN` files with the rest of the week.

## The recall legend (`recall_legend.yaml`)

The viewer's `LEGEND` rail button opens a strip of the search terms the
user tends to forget ("clamps", "tie downs", …); clicking one fills the
search box and nothing else. `recall_legend.yaml` at the repo root is the
hand-curated source; `python3 tools/recall_legend.py build` writes
`viewer/src/data/recall_legend.json`, which the viewer imports statically —
commit both together. `python3 tools/recall_legend.py suggest` mines
`data/Watch/history.tsv` for product phrases no term covers yet; run it after
appending a history batch and curate what it proposes into generic terms. It
never changes a filter and needs no pipeline step.

## Data retention (`data/` is gitignored; nothing here is on GitHub)

Old auction data is almost entirely disposable — the lots are gone and
`lot_number` is reused week to week, so last week's files are actively
dangerous to have lying around at the paths this week's build reads (see
step 5). `data/` runs ~230 MB after two weeks, most of it raw scrapes.

Prior weeks live in `data/archive/<YYYY-MM-DD>/` (gitignored), so
`data/categorized/` only ever holds the current week plus two tracked files —
`README.md` and `auction_703264_categorized.json`, which is a **test fixture
used by `build/tests/test_transform_sample_shape.py`**. Never move or delete
that one.

At the start of a run, sweep the previous week out of the way:
```bash
mkdir -p data/archive/<LAST_RUN_DATE>
mv data/categorized/auction_combined_*.json data/archive/<LAST_RUN_DATE>/ 2>/dev/null
rm -f data/categorized/auction_*_prompt.md data/raw/auction_*.json
```

**Safe to delete outright:**
- `data/raw/auction_*.json` — by far the largest files (~60 MB per week) and
  nothing reads them after step 7. Delete once the deploy is verified.
- `_for_resale.json`, `_resale_groups.json`, `_candidates.json`, `_base.json`,
  `_sweep.json`, `_prefilter.json`, `_flags.json`, `_chunk_NN.json`,
  `_chunk_NN_flags.json`, `_chunk_NN_prompt.md`, `_resale_prompt.md`,
  `_recall.json`, `_recall_flags.json`, `_recall_prompt.md`,
  `_flags_before_recall.json`,
  `_resale_fix*`, `_resale_deduped_before_fix.json`,
  `_flag_groups.json` and `context.yaml` from any prior week — and `_categorized.json` / `_for_agent.json` from any week before last.

The `_chunk_*` files are also the largest of these after the raw scrape (~0.55
MB each, ~4 MB a week). `context.yaml` is regenerated from `buckets.yaml` and
`profile.yaml` on every run, so it is never worth keeping.

**Keep last week's `_categorized.json` AND its `_for_agent.json`.**
`tools/prefilter.py --backtest` replays this week's seeds against last week's
accepted labels and reports per-bucket recall — the only cheap measurement of
whether a seed edit helped. It needs **both**: the labels and the slimmed lots
they were assigned to. One week back is enough. Deleting the `_for_agent.json`
does not degrade the backtest, it makes it impossible — see step 3.

**The other thing worth keeping: resale valuations.** Roughly a third of any
week's lots are products that ran in a previous week (measured: 32.8% of lots,
17.5% of distinct products, week of 2026-07-18 vs 2026-08-01). A valuation for
"SHARK HD430C FLEXSTYLE, Excellent" is just as true this week as last, so
retaining past `_resale_deduped.json` files lets a future run skip re-valuing
anything already priced — worth about another 15 percentage points on top of
the ~18% that `tools/slim_resale.py` already saves.

Nothing reuses them automatically yet, and the 2026-07-18 archive contains no
resale data at all (that week ran before the resale pass existed). From the
2026-08-01 run forward, keep each `auction_<ID>_resale_deduped.json` in its
dated archive folder when clearing the rest.

**And `data/hammer/` — keep it indefinitely.** It is the one thing in `data/`
that becomes *more* useful with age: every file is what real products really
sold for in one closed auction, and that stays true forever. At 2-3.5 MB a
week (measured 2026-09-16) it costs nothing, and each retained week raises the share of this week's
lots that can show a sale history. **Do NOT add it to the step-0 sweep**, and
do not delete from it when clearing a week — the sweep's `find`/`rm` lines
above deliberately touch only `data/categorized/` and `data/raw/`.

Whether to *track* `data/hammer/` in git — which would let a scheduled cloud
job do the Monday pull — is deliberately left open; the default is gitignored,
and `tools/hammer.py --out` is a flag so flipping that later touches nothing
else.

Do not keep old files "just in case" beyond those two. `diff_categorized` is a
within-run resume tool keyed on this week's lot_numbers; it has no use for
prior weeks.

## One-time machine setup (only if commands are missing/erroring)

If `python`, `pip`, or `npm` are "not found," or a `ModuleNotFoundError`
appears (e.g. `curl_cffi`), this machine needs first-time setup:
```bash
sudo apt install python-is-python3
sudo apt install python3-pip
sudo apt install npm
sudo apt install libnss3 libnspr4 libasound2t64
pip install -e . --break-system-packages
cd viewer && npm install && cd ..
git config --global user.name "Perpalicious"
git config --global user.email "<their email>"
```

## Known gotchas

- **Filenames with `(1)`, `(5)` etc. from browser downloads** break bash
  (parentheses are shell syntax) — rename before referencing them in any
  command.
- **`--categorized`/`--resale` paths must exactly match** what's on
  disk, or the build silently proceeds without that data (no crash,
  no error) — this is why step 8's verify is mandatory, not optional.
- **A leftover file from a previous week is the worst failure mode in
  this pipeline.** Every two-auction week writes to the same
  `auction_combined_*.json` paths, and lot numbers repeat: last week's
  categorized file overlapped 93.9% of this week's lot_numbers. Building
  against it succeeds, produces a full-looking bundle, and is wrong on
  nearly every lot. `tools/verify_passes.py` (step 5) compares lot sets
  to catch exactly this — never skip it, and clear old weeks per the
  retention section above.
- **Two-auction weeks**: always prefix lot_numbers before combining, or
  duplicate lot_numbers across auctions corrupt the viewer's per-lot
  state (star/watch, expand).
- **Deploy is local, not `git push`** — `npx gh-pages -d dist -b
  gh-pages` is the only thing that updates the live site. A `git push`
  to `main` alone does nothing to the deployed site.
- **`context.yaml` must be re-attached to every flagging chat** — editing
  `buckets.yaml` or `profile.yaml` in the repo does not update what a chat
  sees. `tools/chunk_flagging.py` regenerates `context.yaml` from both and
  bakes the bucket count into every rendered prompt, which tells the model to
  stop if its own count differs. Concatenating the two removes the older trap
  of attaching one and forgetting the other.
- **The prompt text is in `prompts/`, not `PROMPTS.md`.** Edit
  `prompts/flagging.md` / `prompts/resale.md` to change what a chat is told;
  `PROMPTS.md` is the rationale. Never hand-edit a rendered
  `_prompt.md` — re-run `tools/render_prompts.py <ID>` instead.
- **A mid-week re-scrape overwrites the raw file but keeps `first_seen`.**
  The scraper reads the existing output first and carries each lot's
  `first_seen` forward by item `id`; deleting the raw file before a re-scrape
  makes every lot look new to the SCRAPE filter. Only step 0 should delete
  it. Never build a raw lot into the bundle without a categorized row —
  use the mid-week delta section, not a build flag.
- **Never re-run `tools/chunk_flagging.py` mid-pass.** It rewrites every chunk
  file and the group map, so responses already collected would be reconciled
  against chunks they were never judged from. `tools/expand_flags.py` catches
  the mismatch, but only after the user has spent the chats.
- **A seed typo silently zeroes a bucket.** This is the systemic failure mode
  the prefilter introduces: nothing downstream can distinguish "no lots
  matched this bucket" from "the seed was misspelled". Three things catch it —
  the zero-candidate WARNING in step 3, `--backtest` recall, and the `outside`
  column in step 5's audit. Do not skip the backtest after editing seeds.
- **Bat's List is deliberately narrow — never widen it without the user's
  explicit say-so.** On 2026-09-15 the user cut it from 40% of the auction to
  a targeted list (see SCOPE POLICY at the top of `buckets.yaml` and SCOPE
  LOCK in `profile.yaml`): catch-alls retired, most buckets brand-gated, the
  best ones split. A bucket flagging little is working as intended. If a
  wanted item is missed, add that product or brand to the right bucket; do
  not add "Branded or generic", "flag every X", or a retired bucket back.
  Descriptions that name brands are gates, and the prompt tells the model so.
- **The prefilter must never encode a quality gate.** Buckets whose
  descriptions say "QUALITY or BRANDED ... do NOT flag generic" rely on the
  model applying that bar. Seed them with plain type words so the shortlist
  stays wide; turning the gate into a keyword rule destroys the curation.
- **`slim.py` must show `condition` on most lots, and it now fails if it
  doesn't.** On 2026-09-13 HiBid dropped the `Condition:` label and made the
  grading the whole description; `condition` parsed as None everywhere, and
  the old key-count check still printed 100%. `scraper/condition.py` handles
  the bare form now. If it ever breaks again, the passes still see the grading
  (it falls through into `description`), but `tools/slim_resale.py` groups
  on the field and collapses to title-only — 16% of lots then inherit a
  valuation from a different condition. `tools/regroup_resale.py <ID> plan`
  / `apply` repairs that after the fact with one ~3,000-row chat instead of a
  full re-run; it keeps every valuation whose representative still lands in
  the corrected group.
- **The build is lenient by design** (`--drop-orphans`, tolerant of
  missing optional fields) — this is good for robustness but means
  mistakes fail silently rather than loudly. Verification steps exist
  specifically to compensate for this; never skip them to save time.
