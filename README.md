# Encore Lot Browser — Operator Manual

## What this is

The Encore Lot Browser replaces the slow, hard-to-use HiBid website with a fast, searchable browser you run on your own computer. Each week you scrape the auction's lot data directly from HiBid, send it through your ChatGPT Auction Agent to flag Bat's List items and Nice Picks, then build and open the viewer — a clean four-tab grid that lets you search, filter, star lots, and flip between light and dark mode.

The pipeline has four steps and runs in about a minute once set up. The categorization step (deciding what goes on Bat's List, what's a Nice Pick, scoring confidence) happens entirely inside your ChatGPT Workspace Agent and is not part of this codebase. The code here handles fetching the raw data, turning the Agent's output into a viewer-ready file, and displaying it.

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

### Step 1 — Scrape the auction

Find the auction ID in the URL on encoreauctions.hibid.com. For example, if the catalog page URL is `https://encoreauctions.hibid.com/catalog/741675`, the ID is `741675`.

```bash
source .venv/bin/activate   # if not already active
python -m scraper --auction-id <AUCTION_ID> --output data/raw/auction_<AUCTION_ID>.json
```

This pulls all lots from HiBid and saves them as a JSON file. If you get a Cloudflare 403 error, see the Troubleshooting section below.

### Step 2 — Run the Auction Agent

1. Open ChatGPT Enterprise and go to your Auction Agent.
2. Drag the file `data/raw/auction_<AUCTION_ID>.json` into the chat.
3. Wait for the Agent to return a categorized JSON file. This is where Bat's List flagging, Nice Picks, and confidence scoring happen.
4. Save the returned file as:
   ```
   data/categorized/auction_<AUCTION_ID>_categorized.json
   ```

### Step 3 — Build the viewer data

```bash
python -m build \
  --raw         data/raw/auction_<AUCTION_ID>.json \
  --categorized data/categorized/auction_<AUCTION_ID>_categorized.json \
  --output      viewer/src/data/auction_bundle.json
```

This **joins** the two files on lot number and produces the bundle the viewer reads. The raw scrape supplies titles, images, lot URLs, descriptions and conditions; the categorized file supplies categories, Bat's List flags, Nice Picks and confidence scores.

Both files must describe the same auction. If any categorized lot can't be matched to a raw lot, the script lists the unmatched ones and exits without writing a partial bundle — re-run the scraper for that auction and re-upload to the Agent so the two files line up.

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
Then open `http://localhost:4173/encore-browser/` in your browser. You should see all lots across four tabs: All, Bat's List, Nice Picks, and Watched.

> **One-time GitHub Pages setup.** In your repo settings → Pages → **Source: GitHub Actions** (not "Deploy from a branch"). This needs to be done once; after that, every push to `main` redeploys automatically.

---

## Updating Bat's List

Bat's List rules live inside your ChatGPT Auction Agent's instructions and files panel — not in this codebase. To change which categories or keywords get flagged, open the Agent in ChatGPT Enterprise and edit its instructions there. No code changes are needed here.

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

- **Automated categorization** — categorization is handled entirely by your external ChatGPT Auction Agent, not by code here.
- **Programmatic HiBid login** — the scraper uses token-paste mode only. You copy a token from your browser once per session.
- **Two-day (Sunday + Monday) auction merging** — if an auction spans two days, run the scraper for each day and process them separately for now.
- **Conflict detection between auctions** — no cross-auction deduplication.
- **Accessibility audit** — basic keyboard navigation is present; a full WCAG audit has not been done.
- **Mobile gestures** — tap to expand works; swipe gestures are not implemented.
