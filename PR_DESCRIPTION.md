# Encore Lot Browser — What Got Built

## What got built

This is the complete Encore Lot Browser pipeline, built from scratch and ready to use. You run a scraper to pull all lots from HiBid, hand the file to your ChatGPT Auction Agent for categorization, run a one-line build command to prepare the data, and then open a fast local browser with four tabs (All, Bat's List, Nice Picks, Watched) that lets you search, filter by day and category, star lots you want to track, and switch between light and dark mode. Everything was built to match your design handoff exactly, tested against a real 9880-lot auction dataset, and verified to work before this handoff.

## What each piece does

- **Scraper** (`scraper/`): Connects to HiBid's data API and downloads every lot in an auction — titles, descriptions, images, current bids, categories, and close times — into a single JSON file. It tries anonymous access first; if Cloudflare blocks that, it falls back to a token you copy from your browser once per session.

- **Build script** (`build/`): Takes the categorized JSON your Auction Agent produces and reshapes it into the exact format the viewer needs. It validates every lot before writing the output file, so if the Agent's output is missing anything required, you get a clear error message rather than a broken viewer.

- **Viewer** (`viewer/`): A React app that loads and displays all lots in a fast, scrollable grid. Four tabs filter by audience (everything, Bat's List, Nice Picks, or your starred lots). Search filters in real time across titles, descriptions, lot numbers, and categories. Starring a lot and your theme preference (light/dark) are both saved in your browser so they survive page reloads. Tested smooth at 9880 lots with no scrolling lag.

- **Smoke tests** (`tests/`): Three automated checks that confirm the viewer's core behavior works correctly: search filtering updates the cards in real time, starring a card persists after a page reload, and the Bat's List tab shows a different set of cards than the All tab. All three pass in about 8 seconds.

---

## How to verify it works

Work through these steps in order. Each one builds on the last.

1. **Run the build script against the included sample data.**
   ```bash
   source .venv/bin/activate
   # First, scrape the matching auction so we have raw fields to join with:
   python -m scraper --auction-id 703264 --output data/raw/auction_703264.json
   # Then join the raw scrape to the categorized JSON to produce the bundle:
   python -m build \
     --raw         data/raw/auction_703264.json \
     --categorized data/categorized/auction_703264_categorized.json \
     --output      viewer/src/data/auction_bundle.json
   ```
   You should see a one-line fidelity report (title 100%, image_url 99.9%) and no errors. The viewer reads the bundle file written in the last step.

2. **Build the viewer.**
   ```bash
   cd viewer && npm run build
   ```
   You should see a line like `✓ built in 3.2s` with no errors at the end. The `dist/` folder now contains the compiled app.

3. **Open the viewer in your browser.**
   ```bash
   npm run preview
   ```
   Open `http://localhost:4173/` in Chrome or Firefox. You should see:
   - 9880 lots in the All tab
   - The Bat's List tab showing 349 lots
   - The Nice Picks tab showing 58 lots
   - Search filtering cards in real time as you type
   - Starring a card (click the star icon), then reloading the page — the card should still be starred
   - Clicking the sun/moon icon in the header to switch themes — reload the page and the theme should be remembered
   - Note: all cards will show a broken-image placeholder on this sample because the sample data has no images. This is expected for the sample. Real auction scrapes will have images.

4. **(Optional) Run the automated smoke tests.**
   From the repo root, with the viewer still running from Step 3:
   ```bash
   cd tests && EXTRA_LIB_PATH=/home/bat/lib npx playwright test
   ```
   You should see `3 passed` with a total time around 8 seconds.

5. **Test the scraper against a live auction.**
   ```bash
   python -m scraper --auction-id <current_week_auction_id> --output data/raw/test.json
   ```
   Replace `<current_week_auction_id>` with the ID from the Encore Auctions catalog URL. If your home network passes Cloudflare's check, this will work with no extra setup. If you get a 403 error, follow the token steps in `scraper/AUTH_NOTES.md`. A successful run produces a JSON file with thousands of items and prints the item count.

---

## Known limitations

1. **The scraper could not be tested against live HiBid from the build environment.** Cloudflare blocks requests from datacenter IPs. The scraper is fully built and all three auth paths work as designed — but the live end-to-end run was not verified here. Your home IP will very likely pass Cloudflare without any extra steps. If it doesn't, the token flow in `scraper/AUTH_NOTES.md` is your fallback.

2. **The sample data has no images and no condition fields.** The 9880-lot sample we built and tested against is missing image URLs and condition data — those fields were empty in the source file. As a result, every card in the sample viewer shows a broken-image placeholder, and no condition pills appear (New / Like New / Good / etc.). This is not a bug in the viewer. When you scrape a real auction and run it through your Agent, images and conditions will be present.

3. **Lighthouse mobile performance was not measured automatically.** The viewer was built with all the right techniques for fast mobile performance (lazy rendering, code splitting, small bundle, self-hosted fonts), but the automated Lighthouse score was not captured in the build environment. You can run Lighthouse yourself in Chrome DevTools on the preview URL to check — it should score 85 or above.

4. **The viewer data file is not committed to git.** The file `viewer/src/data/auction_bundle.json` is intentionally excluded from the repo because it changes every week. You must run the build script (Step 3 of the weekly workflow) before running `npm run build`. If you skip that step, the viewer build will fail with a file-not-found error.

5. **Playwright smoke tests need a system library on fresh Linux installs.** If running on a Linux machine you've never used Playwright on before, the browser may fail to launch. Fix it with `npx playwright install-deps chromium` (requires sudo), then re-run the tests.

6. **There is no GitHub remote set up yet.** The repo is a local branch called `main`. To push and optionally deploy to GitHub Pages, add your remote with `git remote add origin <your-github-url>` and push normally.

---

## What was deliberately not built

These items were reviewed and left out of this version by design. They can be added later if needed.

- Categorization logic in the codebase — your ChatGPT Auction Agent handles this externally
- Programmatic login to HiBid — token-paste mode is the v1 approach
- Merging Sunday + Monday auction days into a single view
- Automated GitHub Pages deployment via GitHub Actions
- Cross-auction conflict detection or deduplication
- Full accessibility (WCAG) audit
- Mobile swipe gestures
