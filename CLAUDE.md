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

### 0. Sync, then sweep last week aside

```bash
git pull
```

Then move the previous week out of the way. This is not optional — last week's
`_categorized.json` and `_resale.json` sit at exactly the paths this week's
build reads, and lot numbers repeat across weeks (93.9% overlap measured), so
building against them succeeds and is wrong on nearly every lot:

```bash
mkdir -p data/archive/<LAST_RUN_DATE>
find data/categorized -maxdepth 1 -name 'auction_*.json' \
  ! -name 'auction_703264_categorized.json' \
  -exec mv -t data/archive/<LAST_RUN_DATE>/ {} +
rm -f data/categorized/context.yaml data/raw/auction_*.json
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
with a broken one.

Then build the flagging pass's chunks:
```bash
python3 tools/chunk_flagging.py <ID>
```
Dedups the auction to one row per distinct product, cuts it into numbered
chunk files, and concatenates `buckets.yaml` + `profile.yaml` into a single
`data/categorized/context.yaml`. Check its printout:
- **the exact upload list** — normally 7 chunks plus `context.yaml`, 8 files
- the bucket count (62 as of 2026-08-30). If a read-test in a fresh ChatGPT
  chat reports a different number, `context.yaml` did not attach
- dedup normally collapses 20-25% of lots (25,195 → 19,250 on 2026-08-30)
- each chunk's row count and last `lot_number` — both go into that chunk's
  prompt, replacing `N` and `<LAST LOT>`

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
more**. It reaches only 77.4% of lots actually bid on, and of 234 real bids 94
(40%) match no seed at all (`data/Watch/FINDINGS.md`). Since 2026-08-30 it is
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

Tell the user: *"Eight files are ready — `tools/chunk_flagging.py` printed the
exact list.

**Attach `data/categorized/context.yaml` to EVERY chat.** It is `buckets.yaml`
and `profile.yaml` in one file.

Then run one chat per chunk, same prompt every time:
- `auction_<ID>_chunk_01.json` → save as `auction_<ID>_chunk_01_flags.json`
- ...and so on for each chunk

`PROMPTS.md` § Pass 1 has the prompt. Replace `N` with that chunk's row count
and `<LAST LOT>` with its last `lot_number` — both printed above.

Let me know when they're saved and I'll continue."*

The names matter. Each response must be saved under **its own chunk number**;
`tools/expand_flags.py` checks every response against the chunk it belongs to,
so a file saved under the wrong number fails rather than merging silently.

The pass returns **matches only** and must end with
`{"chunk_complete": "<last lot_number>"}`. That sentinel is the truncation
detector — a response that stops early loses its tail, so a missing or wrong
sentinel is caught in step 5.

If the week also needs resale, hand off `auction_<ID>_for_resale.json` → save
as `auction_<ID>_resale_deduped.json` in its own chat, with **no** config files
attached (`docs/PASS_SOURCES.md`: the resale pass has no notion of buckets).

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
  --output viewer/src/data/auction_bundle.json --drop-orphans
```
Drop the `--resale` line on a flagging-only week; the build treats resale as
optional and every lot simply keeps a null valuation.

Check the build's own output for:
- `category_path` coverage ~100%
- resale coverage ~matches total lot count (or 0 on a flagging-only week)
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
rm -f data/raw/auction_*.json
```

**Safe to delete outright:**
- `data/raw/auction_*.json` — by far the largest files (~60 MB per week) and
  nothing reads them after step 7. Delete once the deploy is verified.
- `_for_resale.json`, `_resale_groups.json`, `_candidates.json`, `_base.json`,
  `_sweep.json`, `_prefilter.json`, `_flags.json`, `_chunk_NN.json`,
  `_chunk_NN_flags.json`, `_flag_groups.json` and `context.yaml` from any prior
  week — and `_categorized.json` / `_for_agent.json` from any week before last.

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
  prints the bucket count; if a read-test in a fresh chat returns a different
  number, flag it to the user before they run the full pass. Concatenating the
  two removes the older trap of attaching one and forgetting the other.
- **Never re-run `tools/chunk_flagging.py` mid-pass.** It rewrites every chunk
  file and the group map, so responses already collected would be reconciled
  against chunks they were never judged from. `tools/expand_flags.py` catches
  the mismatch, but only after the user has spent the chats.
- **A seed typo silently zeroes a bucket.** This is the systemic failure mode
  the prefilter introduces: nothing downstream can distinguish "no lots
  matched this bucket" from "the seed was misspelled". Three things catch it —
  the zero-candidate WARNING in step 3, `--backtest` recall, and the `outside`
  column in step 5's audit. Do not skip the backtest after editing seeds.
- **The prefilter must never encode a quality gate.** Buckets whose
  descriptions say "QUALITY or BRANDED ... do NOT flag generic" rely on the
  model applying that bar. Seed them with plain type words so the shortlist
  stays wide; turning the gate into a keyword rule destroys the curation.
- **The build is lenient by design** (`--drop-orphans`, tolerant of
  missing optional fields) — this is good for robustness but means
  mistakes fail silently rather than loudly. Verification steps exist
  specifically to compensate for this; never skip them to save time.
