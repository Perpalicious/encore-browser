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

Pull **before** `python -m classify prepare`, never during a run: a change to
`CLAUDE.md`, `buckets.yaml`, `profile.yaml` or the prompt arriving mid-run
changes the fingerprint and invalidates chunks already ingested.

Then move the previous week out of the way. This is not optional — last week's
`_categorized.json` and `_resale.json` sit at exactly the paths this week's
build reads, and lot numbers repeat across weeks (93.9% overlap measured), so
building against them succeeds and is wrong on nearly every lot:

```bash
mkdir -p data/archive/<LAST_RUN_DATE>
mv data/categorized/auction_combined_*.json data/archive/<LAST_RUN_DATE>/ 2>/dev/null
rm -f data/raw/auction_*.json
```

`<LAST_RUN_DATE>` is the previous run's date (`ls data/archive/` shows what is
already there; the files' own mtimes show which week is currently in
`data/categorized/`). The tracked fixture `auction_703264_categorized.json` is
not matched by that glob and must stay. See the retention section at the end
for what is safe to delete afterwards.

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

### 3. Slim, then shortlist (builds both passes' inputs)
```bash
python3 tools/slim.py <ID>
```
Writes `data/categorized/auction_<ID>_for_agent.json` and prints per-field
coverage. Sanity-check that printout before continuing:
- `lot_number`, `title`, `category` must all be 100%
- `model` is normally ~75-80%, `size` ~35% — near-zero on either means
  HiBid changed its `description_raw` field names and `tools/slim.py`
  needs its key mapping updated

`tools/slim.py` reparses `description_raw` to recover `model`, `size`,
`notes`, and damage/missing-parts detail, which the scraper strips out and
drops. Do not replace this step with a quick inline one-liner over
`description` — that field is empty on essentially every lot, so a naive
slim hands the ChatGPT passes almost nothing to work with. See the
docstring in `tools/slim.py` for why.

Then build the resale pass's smaller input:
```bash
python3 tools/slim_resale.py <ID>
```
These auctions repeat the same product heavily (58 identical lots is normal),
so the resale pass values one representative per distinct product and the
result is fanned back out in step 5. Expect ~15-25% fewer rows. This is a
pure dedup, not a junk filter — every lot still ends up valued, and the
grouping key includes condition and damage so a sealed unit is never averaged
with a broken one. Only the resale pass uses this file.

Then shortlist candidates for the flagging pass:
```bash
python3 tools/prefilter.py <ID>
```
Writes `_candidates.json` (the model's input), `_base.json` (an all-false row
for every lot, so coverage is guaranteed without spending tokens on obvious
non-matches), `_sweep.json`, and `_prefilter.json`. Check its printout:
- candidate count is normally ~35-40% of the auction (~10k rows)
- no bucket exceeds the 8% share guard and no `Error:` lines
- **zero-candidate buckets are listed as a WARNING** — a seed typo looks
  exactly like this, and that bucket will score no matches all week
- the paste boundaries at the end are for the older manual flow; the
  flagging pass is chunked by `python -m classify prepare` now and ignores them

Why the shortlist exists: the flagging pass used to judge all ~27k lots
against all 45 buckets with an ~85% negative rate, and narrow buckets
starved. Measured on 2026-08-15, 77 lots had KEYBOARD in the title and 5 were
flagged; storage bins scored 4 of 36. See the docstring in
`tools/prefilter.py`.

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
entirely different lots. That does not read as an error; it reads as a
catastrophic seed regression. Measured 2026-08-16 on identical seeds: **33.4%
cross-week vs 98.0% correctly paired.** The tool now aborts on this rather than
printing the bogus table, and the abort message repeats the commands above.

Reports per-bucket recall against last week's accepted labels. **LOT recall
must stay at or above 97%** (currently 98.0%). PAIR recall is lower (~96%) and
partly reflects errors in the old labels themselves — it flagged wifi routers
as Power tools because of the word "router" — so treat the per-bucket table as
a lead, not a verdict.

This is also why `_for_agent.json` is now worth keeping one week back (see the
retention section) — without it the backtest cannot be run correctly at all.

Then split the auction into the four flagging passes:
```bash
python3 tools/split_passes.py <ID>
```
Writes `_pass_a.json` … `_pass_d.json` and asserts every lot lands in exactly
one. **This covers 100% of lots — the prefilter shortlist does not.** Measured
against three months of real bid/watch history, the shortlist alone reached
only 77.4% of lots actually bid on. See `passes.yaml` for why there are four.

`tools/prefilter.py` still runs: `_base.json` guarantees coverage, and
`--backtest` / `--audit` remain the cheap way to measure seed quality.

### 4. Flagging passes — automated. Resale — still a handoff.

#### 4a. The four flagging passes

```bash
python -m classify prepare <ID>
```

Splits each pass into chunks of at most 500 lots (or ~150 KB, whichever comes
first) and writes a per-pass `PROMPT.md` with the full `buckets.yaml` and
`profile.yaml` inlined. Expect ~56 chunks for a normal week.

Then loop:

```bash
python -m classify status <ID>     # prints a DISPATCH block: one line per chunk
python -m classify ingest <ID>     # validate whatever workers have written
```

For every line in the DISPATCH block, spawn a **`lot-classifier`** subagent
(Sonnet, Read+Write only, defined in `.claude/agents/lot-classifier.md`).
Send several Agent calls per message so they run concurrently — waves of about
ten. Each worker's task message is only this:

> Read `<prompt path>` and follow it exactly.
> chunk id: `<chunk id>` · input: `<input path>` · output: `<output path>`
> rows: `<n>` · fingerprint: `<fingerprint>`
> Reply with the single status line and nothing else.

**Never let the classified rows into your own context.** A week is ~0.7M
output tokens; workers write their own files and `ingest` reads them. If you
find yourself reading a chunk output or an `ingested/` file, stop — that is
the one thing this design exists to prevent.

Re-run `ingest` then `status` until it says all chunks are ingested. `status`
exits non-zero while anything is outstanding, so it is safe to loop on.
Chunks that fail validation are retried once and then bisected automatically
(500 → 250 → 125 …); a chunk still failing at the floor is reported as
**BLOCKED** with its lot numbers and the exact errors. Report blocked chunks
to the user — do not route around them, and do not hand-edit an output file.

```bash
python -m classify finalize <ID>
```

Writes `auction_<ID>_flags_<a|b|c|d>.json`, and refuses if any lot is
unaccounted for. It also prints per-pass flagged / subtyped / multi-bucket /
pick counts — glance at these before moving on, especially **pass A**: near-zero
flags there means the personal-care buckets did not attach (see
`docs/PASS_SOURCES.md`).

**On staleness.** Every chunk records a fingerprint covering the input, the
prompt, `buckets.yaml`, `profile.yaml`, `passes.yaml`, the contract version,
the worker definition, the effective Claude instruction stack, and the pinned
model id. Editing any of them mid-run invalidates the affected results rather
than blending two configurations — `prepare` says so and discards them, and
`finalize` refuses while a pass is stale. So land config or doc edits *before*
starting a run, not during one.

#### 4b. STOP — hand the resale pass to the user

Tell the user: *"The flagging passes are done. One file left for you:*

*- `auction_<ID>_for_resale.json` → save as `auction_<ID>_resale_deduped.json`*

*`PROMPTS.md` has the resale prompt. Let me know when it's saved and I'll
continue."*

The name matters: the resale pass returns `_resale_deduped.json`, **not**
`_resale.json`; step 5 generates that from it, and writing it directly would
leave most lots unvalued.

`docs/PASS_SOURCES.md` maps each pass to the exact files that supply its
prompt, config and data, and lists the assumptions that break an automated run
(chief among them: never slice `buckets.yaml` down to a pass's
`focus_buckets`).

Do not proceed past this point until the user confirms the resale file exists.


### 5. Assemble the categorized file, expand resale, then verify

Chain all four flag files onto the all-false base so every lot has a row,
feeding each output into the next. Order does not matter — each pass owns a
disjoint set of lot_numbers:
```bash
python -m merge_categorized --existing data/categorized/auction_<ID>_base.json \
  --new data/categorized/auction_<ID>_flags_a.json --output /tmp/cat_a.json
python -m merge_categorized --existing /tmp/cat_a.json \
  --new data/categorized/auction_<ID>_flags_b.json --output /tmp/cat_b.json
python -m merge_categorized --existing /tmp/cat_b.json \
  --new data/categorized/auction_<ID>_flags_c.json --output /tmp/cat_c.json
python -m merge_categorized --existing /tmp/cat_c.json \
  --new data/categorized/auction_<ID>_flags_d.json \
  --output data/categorized/auction_<ID>_categorized.json
```
Each step reports `Merged <n_added> new items` — **`n_added` must be 0 every
time.** Anything else means that pass returned a `lot_number` that isn't in
this week's auction, which is either a hallucinated row or a stale file. Stop
and investigate, naming which pass.

This step also carries the `lot_set_sha` stamped into `_base.json` through to
the categorized file, which verify checks in the next step.

Now fan each product's valuation back out to every lot in its group:
```bash
python3 tools/expand_resale.py <ID>
```
This reads `_resale_deduped.json` plus the group map from step 3 and writes
`auction_<ID>_resale.json`. It exits non-zero and writes nothing if any
product went unvalued — which is the signature of a truncated ChatGPT run.
If that happens, tell the user which products are missing and have them
re-run that portion; do not hand-patch the file.

Now verify both pass outputs:
```bash
python3 tools/verify_passes.py <ID>
```
This checks required fields, duplicate lot_numbers, and that each file's
lot_numbers match **this week's** slimmed file. That last check is the one
that matters: two-auction weeks all write to `auction_combined_*.json`, and a
previous week's file overlaps ~94% of this week's lot numbers, so a stale file
builds cleanly into a completely wrong bundle. Row counts alone will not catch
it; the `lot_set_sha` comparison catches it exactly.

It now **fails** (not just reports) on: `bats_subtype` coverage under 90% of
flagged lots, bucket names absent from `buckets.yaml`, any `bats_category` key,
`is_bats_list` disagreeing with `bats_buckets`, and `personal_reasoning`
missing from more than 5% of picks. Each of those produces a clean-looking
build with wrong or missing data; the 0%-subtype run of 2026-08-15 shipped
precisely because this script reported and exited 0.

It also prints a per-bucket `shown / kept / rate` table. Two shapes to report
to the user:
- **a bucket shown ≥20 candidates and keeping none** — the pass refused the
  whole bucket, which is the exact failure this pipeline exists to fix
- **a rate above 95%** — the shortlist is doing the judging, so that bucket's
  seeds have become a whitelist and its `description` is no longer deciding

The `outside` column counts buckets assigned outside the shortlist. That is the
prefilter's own recall gap; feed it back with
`python3 tools/prefilter.py <ID> --audit data/categorized/auction_<ID>_flags.json`,
which also mines candidate new seeds from the accepted titles.

If verify fails, report exactly what it said to the user and stop. Do not
proceed with a malformed, stale, or markdown-wrapped file.

### 6. Build the bundle
```bash
python -m build --raw data/raw/auction_<ID>.json \
  --categorized data/categorized/auction_<ID>_categorized.json \
  --resale data/categorized/auction_<ID>_resale.json \
  --output viewer/src/data/auction_bundle.json --drop-orphans
```

Check the build's own output for:
- `category_path` coverage ~100%
- resale coverage ~matches total lot count
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
  `_sweep.json`, `_prefilter.json`, `_flags.json` from any prior week — and
  `_categorized.json` / `_for_agent.json` from any week before last.

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
- **The `buckets.yaml` / `profile.yaml` re-upload problem is gone for
  flagging.** `python -m classify prepare` inlines both from disk on every
  run, and each worker reports how many buckets it actually read — `ingest`
  compares that against the count parsed from `buckets.yaml` and rejects a
  mismatch. The gotcha still applies to the **resale** pass, which is a manual
  paste; note that pass takes neither file (`docs/PASS_SOURCES.md`).
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
