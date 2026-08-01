# Encore Lot Browser — Project Instructions

This repo scrapes weekly HiBid/Encore auctions, runs them through three
ChatGPT passes (Bat's List flagging, resale valuation, personal-match),
builds a static bundle, and deploys it to GitHub Pages via a local
`gh-pages` branch push (NOT via GitHub Actions — the repo is capped on
Actions storage, so deploys must go through `npx gh-pages`, never `git
push` to trigger a workflow).

Machine paths: desktop (Grink) = `~/projects/encore-browser`, laptop
(Chickalettis) = `~/code/encore-browser`. Always confirm which machine
you're on and use the right path.

## When the user asks to run this week's auction

Ask for the auction ID(s) if not already given. Then follow this
sequence exactly. **Stop and wait for the user at the marked points —
the three ChatGPT passes cannot be run by you; they require the user to
paste the slimmed file into a ChatGPT chat and paste the response back.**

### 0. Sync
```bash
git pull
```

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

### 3. Slim (feeds all three ChatGPT passes)
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
with a broken one. Only the resale pass uses this file; flagging and
personal-match still read the full slimmed file.

### 4. STOP — hand off to the user

Tell the user: *"Two files are ready:
- `data/categorized/auction_<ID>_for_agent.json` — for the Bat's List
  flagging pass and the personal-match pass
- `data/categorized/auction_<ID>_for_resale.json` — for the resale pass
  only (deduplicated, so it's smaller)

Please run the three ChatGPT passes and give me back three files:
- `data/categorized/auction_<ID>_categorized.json`
- `data/categorized/auction_<ID>_resale_deduped.json`  ← note the name
- `data/categorized/auction_<ID>_personal.json`

Let me know when they're saved and I'll continue."*

The resale pass returns `_resale_deduped.json`, NOT `_resale.json` —
step 5 generates `_resale.json` from it. Writing the pass output
straight to `_resale.json` would leave most lots unvalued.

The prompt to use for each of the three passes is in `PROMPTS.md`,
along with the output-shape rules each pass must follow. If the user
asks what to paste into ChatGPT, point them there rather than
improvising a prompt.

Do not proceed past this point until the user confirms all three files
exist.

### 5. Expand the resale file, then verify all three

Fan each product's valuation back out to every lot in its group:
```bash
python3 tools/expand_resale.py <ID>
```
This reads `_resale_deduped.json` plus the group map from step 3 and writes
`auction_<ID>_resale.json`. It exits non-zero and writes nothing if any
product went unvalued — which is the signature of a truncated ChatGPT run.
If that happens, tell the user which products are missing and have them
re-run that portion; do not hand-patch the file.

Now verify all three pass outputs:
```bash
python3 tools/verify_passes.py <ID>
```
This checks required fields, duplicate lot_numbers, and that each file's
lot_numbers match **this week's** slimmed file. That last check is the one
that matters: two-auction weeks all write to `auction_combined_*.json`, and a
previous week's file overlaps ~94% of this week's lot numbers, so a stale file
builds cleanly into a completely wrong bundle. Row counts alone will not catch
it.

If verify fails, report exactly what it said to the user and stop. Do not
proceed with a malformed, stale, or markdown-wrapped file.

### 6. Merge personal-match fields into the categorized file
```bash
python3 -c "
import json
cat = json.load(open('data/categorized/auction_<ID>_categorized.json'))
personal = json.load(open('data/categorized/auction_<ID>_personal.json'))
cat_items = cat.get('items', cat) if isinstance(cat, dict) else cat
personal_items = personal.get('items', personal) if isinstance(personal, dict) else personal
personal_by_lot = {p['lot_number']: p for p in personal_items}
merged = 0
for c in cat_items:
    p = personal_by_lot.get(c['lot_number'])
    if p:
        c['personal_match'] = p.get('personal_match')
        c['personal_tags'] = p.get('personal_tags')
        c['match_strength'] = p.get('match_strength')
        c['match_types'] = p.get('match_types')
        c['personal_reasoning'] = p.get('reasoning')
        merged += 1
out = cat_items if not isinstance(cat, dict) else cat
json.dump(out, open('data/categorized/auction_<ID>_categorized.json', 'w'))
print(f'Merged personal fields into {merged}/{len(cat_items)} items')
"
```

### 7. Build the bundle
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

### 8. Verify the bundle (non-negotiable — this is the step that catches
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
"
```
Report these numbers to the user. If resale or personal_match coverage
is 0 or unexpectedly low, STOP and investigate — do not deploy. Likely
causes: a filename mismatch between what was merged/built and what's on
disk, or a `--categorized`/`--resale` flag pointing at a stale file.

### 9. Deploy
```bash
cd viewer && npm run build && npx gh-pages -d dist -b gh-pages && cd ..
```
`npm run build` MUST run after step 7 (bundle regeneration) — if a stale
`dist` exists from an earlier build, this step must rebuild it fresh, or
the deploy will ship old data. Never run `npx gh-pages` without a fresh
`npm run build` immediately before it in the same sequence.

Tell the user the deploy is live at
`https://perpalicious.github.io/encore-browser/` and suggest they hard
refresh (Ctrl+Shift+R) or check in an incognito window if the CDN is
slow to update (can take 1-3 minutes).

### 10. Commit and push to `main` (backs up code + data; does NOT trigger
a deploy — deploy already happened in step 9 via `gh-pages`)
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
- `_for_agent.json`, `_for_resale.json`, `_resale_groups.json`,
  `_categorized.json`, `_personal.json` from any prior week.

**The one thing worth keeping: resale valuations.** Roughly a third of any
week's lots are products that ran in a previous week (measured: 32.8% of lots,
17.5% of distinct products, week of 2026-07-18 vs 2026-08-01). A valuation for
"SHARK HD430C FLEXSTYLE, Like New" is just as true this week as last, so
retaining past `_resale_deduped.json` files lets a future run skip re-valuing
anything already priced — worth about another 15 percentage points on top of
the ~18% that `tools/slim_resale.py` already saves.

Nothing reuses them automatically yet, and the 2026-07-18 archive contains no
resale data at all (that week ran before the resale pass existed). From the
2026-08-01 run forward, keep each `auction_<ID>_resale_deduped.json` in its
dated archive folder when clearing the rest.

Do not keep old files "just in case" beyond that. `diff_categorized` is a
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
- **`buckets.yaml` changes must be re-uploaded to the ChatGPT flagging
  pass** — editing the file in the repo does not update what the chat
  sees; the user must re-attach it. There are currently 45 buckets; if
  a bucket-name read-test in a fresh chat returns a different number,
  flag it to the user before they run the full categorization pass.
- **The build is lenient by design** (`--drop-orphans`, tolerant of
  missing optional fields) — this is good for robustness but means
  mistakes fail silently rather than loudly. Verification steps exist
  specifically to compensate for this; never skip them to save time.
