# Encore Lot Browser — Operator Manual

## What this is

The Encore Lot Browser replaces the slow, hard-to-use HiBid website with a fast, searchable browser you run on your own computer. Each week you scrape the auction's lot data directly from HiBid, send it through your ChatGPT Auction Agent to flag Bat's List items, then build and open the viewer — a clean three-tab grid (All / Bat's List / Watched) that lets you search, drill through HiBid's category tree, star lots, and flip between light and dark mode.

The pipeline has four steps and runs in about a minute once set up. **Categories come straight from HiBid's own category tree** — the viewer lets you drill down through it (e.g. Home Goods & Decor → Home Goods → Bed / Bath Items). The Auction Agent's only job now is flagging Bat's List items; it no longer assigns categories. **Search is fuzzy and typo-tolerant** (a search for "wustof" finds "Wüsthof"; "kitchenad" finds "KitchenAid"). The code here handles fetching the raw data, joining it with the Agent's Bat's List flags, and displaying it.

---

## Prerequisites

You need Python 3.11 or newer and Node.js 22 or newer (any current LTS release works).

**macOS**
```bash
brew install python@3.11 node
```

**Linux (Debian/Ubuntu)**
```bash
sudo apt update && sudo apt install python3.11 python3.11-venv nodejs npm
```

Verify your versions:
```bash
python3 --version   # should print 3.11.x or higher
node --version      # should print v22.x.x or higher
```

---

## One-time setup

Run these once after cloning the repo. You only need to do this again if you wipe your environment.

```bash
# 1. Clone and enter the repo
git clone <your-repo-url> encore-browser
cd encore-browser

# 2. Set up the Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Install the viewer's JavaScript dependencies
cd viewer && npm install && cd ..

# 4. (Optional) Install test dependencies — only needed if you want to run the smoke tests
cd tests && npm install && cd ..

# 5. Copy the environment template
cp .env.example .env
```

The `.env` file is where you put your HiBid token when needed (see Troubleshooting below). It is never committed to git.

---

## The weekly workflow

Auctions grow as items are added throughout the week. The scraper is cheap to re-run (~80 s for 20k items), but the Auction Agent is the expensive step (~30 min for a full pass). So the **default** weekly flow is **incremental**: re-scrape everything, but only send the *new* lots to the Agent and merge them into the existing categorized file. A full re-categorize is the fallback.

### Step 1 — Re-scrape the auction (always)

Find the auction ID in the URL on encoreauctions.hibid.com. For example, if the catalog page URL is `https://encoreauctions.hibid.com/catalog/741675`, the ID is `741675`.

```bash
source .venv/bin/activate   # if not already active
python -m scraper --auction-id <AUCTION_ID> --output data/raw/auction_<AUCTION_ID>.json
```

This pulls all lots from HiBid and overwrites the raw JSON. If you get a Cloudflare 403 error, see the Troubleshooting section below.

### Step 2 — Categorize just the new lots

**On the first run for a given auction** (no existing categorized file yet), skip to "Full categorize" below.

**On subsequent runs**, extract only the lots that are not yet categorized:

```bash
python -m diff_categorized \
  --raw      data/raw/auction_<AUCTION_ID>.json \
  --existing data/categorized/auction_<AUCTION_ID>_categorized.json \
  --output   data/categorized/auction_<AUCTION_ID>_to_categorize.json
```

You'll see `Found N new lots out of M total raw, K existing categorized.` If `N` is 0, the script exits non-zero and tells you there's nothing to do — skip straight to Step 3.

Otherwise, open ChatGPT Enterprise, go to your Auction Agent, drag in `data/categorized/auction_<AUCTION_ID>_to_categorize.json`, wait for it to return a categorized JSON, save it (any path is fine — e.g. `data/categorized/auction_<AUCTION_ID>_just_new.json`), then merge it back in:

```bash
python -m merge_categorized \
  --existing data/categorized/auction_<AUCTION_ID>_categorized.json \
  --new      data/categorized/auction_<AUCTION_ID>_just_new.json \
  --output   data/categorized/auction_<AUCTION_ID>_categorized.json
```

The merge is in-place (output path matches existing) with an atomic tmp-file rename, so an interrupted run can't corrupt the existing file. New entries override existing ones on a `lot_number` collision — so if you ever need to fix a miscategorization, just re-categorize that one lot and re-run merge.

**Full categorize (fallback / first run).** When you want every lot re-evaluated — e.g. you've updated the Agent's Bat's List rules and want them applied retroactively — drag the **raw** JSON into the Agent and save its full response, overwriting:

```
data/categorized/auction_<AUCTION_ID>_categorized.json
```

Then continue to Step 3.

### Step 3 — Build the viewer data

```bash
python -m build \
  --raw         data/raw/auction_<AUCTION_ID>.json \
  --categorized data/categorized/auction_<AUCTION_ID>_categorized.json \
  --output      viewer/src/data/auction_bundle.json \
  --drop-orphans
```

This **joins** the two files on lot number and produces the bundle the viewer reads. The raw scrape supplies titles, images, lot URLs, descriptions, conditions, **and HiBid's full category tree**; the categorized file supplies only Bat's List flags and confidence scores. (The Agent's own category guesses, if any, are ignored — HiBid's native tree is the source of truth.)

`--drop-orphans` is the recommended default for routine weekly builds. It tolerates the common case where lots have been removed from the auction between scrapes — each orphan categorized item is logged as a `WARNING` with its lot_number and enrichment fields, then excluded from the bundle. A `Dropped N orphan items` summary line confirms how many were skipped.

**Omit `--drop-orphans`** for first-time / debugging runs where you want the build to fail loudly on any mismatch. Without the flag, the script lists the unmatched lots and exits non-zero without writing a partial bundle, which is useful when investigating an unexpected schema drift in the Agent's output.

You'll see a one-line fidelity report like
`Fidelity: title 100% (9880/9880), image_url 99.9% (9870/9880).` —
if `image_url` drops below 95%, viewer cards will mostly show a "NO IMAGE" placeholder; that's a signal the scrape itself was incomplete.

### Step 4 — Commit and push (auto-deploys)

```bash
git add viewer/src/data/auction_bundle.json
git commit -m "Update bundle for <DATE>"
git push
```

A GitHub Actions workflow ([.github/workflows/deploy.yml](.github/workflows/deploy.yml)) watches `main`. On every push it rebuilds the viewer and publishes it to GitHub Pages — usually live within ~60 seconds. You can also trigger a deploy by hand from the Actions tab → **Deploy viewer to GitHub Pages** → **Run workflow**.

The committed bundle (`viewer/src/data/auction_bundle.json`) is what GitHub Pages serves — there is no agent-side data fetching at runtime. Every weekly refresh is one commit of this one file.

### Step 5 — Open the viewer

**Live site (after the deploy workflow finishes):**
```
https://<your-github-user>.github.io/encore-browser/
```

**Preview locally before pushing:**
```bash
cd viewer && npm run preview
```
Then open `http://localhost:4173/encore-browser/` in your browser. You should see all lots across three tabs: All, Bat's List, and Watched. Use the category drop-downs to drill through HiBid's tree, and the search box for fuzzy, typo-tolerant search.

**Bat's List is two-level.** Instead of one long row of bucket chips, the tab opens on a set of **groups** (Kitchen & dining, Tools & garage, Toys & games, …). Pick a group to see its buckets, pick a bucket to see its items, and use the "← All groups" / "← {group}" buttons to step back up. Group and bucket buttons wrap to multiple rows — no sideways scrolling. The grouping comes from the `group:` field on each bucket in `buckets.yaml`, joined in at build time.

> **One-time GitHub Pages setup.** In your repo settings → Pages → **Source: GitHub Actions** (not "Deploy from a branch"). This needs to be done once; after that, every push to `main` redeploys automatically.

---

## Updating Bat's List

Bat's List rules live inside your ChatGPT Auction Agent's instructions and files panel — not in this codebase. To change which categories or keywords get flagged, open the Agent in ChatGPT Enterprise and edit its instructions there. No code changes are needed here.

**Bucket groups** (how flagged buckets are organized into the two-level Bat's List menu) live in `buckets.yaml` — each bucket has a `group:` field. The build joins these to the bundle by bucket name. If a categorized file contains a bucket name that isn't in `buckets.yaml` (e.g. an older auction categorized before a bucket was renamed), the build doesn't fail: it prints a `Warning: … bat bucket(s) … have no group …` line and files those items under an **"Other"** group in the viewer so nothing is lost. To file them properly, add the bucket (with its `group:`) to `buckets.yaml`, or re-categorize the auction with the current Agent.

---

## Troubleshooting

**"Scraper returns a Cloudflare 403 error"**

The scraper tries three auth methods in order: anonymous, cookie-based, then a bearer token. From certain network environments (including cloud/datacenter IPs) Cloudflare blocks the first two. Your home IP should work fine for anonymous access. If it doesn't, you'll need to provide a bearer token:

See `scraper/AUTH_NOTES.md` for exact steps. Short version: log in at hibid.com in your browser, open DevTools, find any GraphQL request, copy the `Authorization: Bearer eyJ...` value, and paste the long token string into your `.env` file as `HIBID_TOKEN=eyJ...`. Tokens expire after a few hours; repeat if you get auth errors.

**"All cards show a broken-image placeholder"**

The categorized JSON file has empty image URLs. This can happen if the scraper run didn't capture images. Re-run Step 1 (the scraper) and then repeat Step 2 through Step 4.

**"Viewer build complains that `auction_bundle.json` is not found"**

You need to run Step 3 (the build script) before building the viewer. The viewer data file is regenerated weekly and committed to git so GitHub Pages can serve it.

**"The GitHub Actions deploy failed with a missing-bundle error"**

The workflow's first check is whether `viewer/src/data/auction_bundle.json` exists. If you committed without running Step 3, that file is stale or missing. Run Step 3, `git add` the bundle, commit, push again.

**"Playwright smoke tests fail to launch the browser"**

On a fresh Linux install, Playwright may be missing some system libraries. Run:
```bash
npx playwright install-deps chromium
```
This requires `sudo`. After it completes, re-run the tests.

**"Condition pills don't appear on cards"**

The `condition` field is optional. If the scrape or the Agent's output didn't include condition data, cards will display without condition pills. This is expected behavior — no action needed.

---

## What is intentionally not included

The following items were reviewed and deliberately left out of scope for this version:

- **Category assignment** — categories come from HiBid's own category tree (captured by the scraper), not from code or the Agent. The Agent only flags Bat's List items.
- **Programmatic HiBid login** — the scraper uses token-paste mode only. You copy a token from your browser once per session.
- **Two-day (Sunday + Monday) auction merging** — if an auction spans two days, run the scraper for each day and process them separately for now.
- **Conflict detection between auctions** — no cross-auction deduplication.
- **Accessibility audit** — basic keyboard navigation is present; a full WCAG audit has not been done.
- **Mobile gestures** — tap to expand works; swipe gestures are not implemented.
