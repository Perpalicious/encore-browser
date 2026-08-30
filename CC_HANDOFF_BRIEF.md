# Claude Code Handoff Brief: Encore Lot Browser

## Project Context

Personal weekly tool for browsing 10–20k Encore Auctions lots without using their slow native site. Pipeline:

```
HiBid GraphQL API → Python scraper → raw JSON
  → user uploads to external ChatGPT Workspace Agent (Auction Agent)
  → enriched JSON
  → Python build script → bundle JSON
  → React+Vite+TS viewer → GitHub Pages
```

The categorization step (Bat's List flagging, Nice Picks, confidence scoring) happens **outside this repo** via a ChatGPT Workspace Agent. Do not build a categorizer here.

The user is **not a coder**. They cannot meaningfully read your diffs. Every PR must include a plain-English summary explaining what changed, what it does, and what behavioral tests confirm it works. The user verifies by behavior, not by code review.

The design handoff is provided alongside this brief in `design_handoff_encore_lot_browser/` — treat it as the canonical UI spec. Match it faithfully using production patterns.

---

## Scope

### Build
1. Python scraper (`scraper/`) hitting HiBid GraphQL API directly
2. Python build/transform script (`build/`)
3. React + Vite + TS viewer (`viewer/`) recreating the design handoff prototype
4. 3 Playwright smoke tests (`tests/`)
5. `README.md` documenting the complete operator workflow

### Do NOT touch
- `bats_list.yaml` if present in repo — user's evolving config, do not modify
- Design tokens from the handoff — use as-is
- The Auction Agent config (lives outside this repo)
- Anything in `.env*` files
- Tests, once written, cannot be modified by later subagents to make code pass

### Out of scope (defer)
- Automated categorization inside the codebase
- GitHub Actions deployment
- Conflict detection between auctions
- Two-day (Sunday + Monday) auction merging — this week is single-day
- Accessibility audit beyond keyboard nav basics
- Mobile gestures beyond tap-to-expand
- Programmatic HiBid login

---

## Scraper Specification

### Endpoint
- **URL:** `https://encoreauctions.hibid.com/graphql`
- **Method:** POST
- **Content-Type:** `application/json`

### Auth strategy (do these in order)
1. **Try anonymous first** — make request with no Authorization header, no cookies. If it returns valid lot data, use this. Document in README.
2. **If anon fails**, make an initial GET to `https://encoreauctions.hibid.com/catalog/{auctionId}` first to acquire session cookies, then include those cookies on subsequent POSTs.
3. **If THAT fails**, read JWT from environment variable `HIBID_TOKEN` (loaded via `python-dotenv`), pass as `Authorization: Bearer {token}`. README must explain how the user copies a fresh JWT from DevTools weekly.

Do **NOT** implement programmatic login. Do **NOT** commit tokens to git. The scraper should redact `HIBID_TOKEN` from any error messages or logs.

### Operation
- **operationName:** `LotSearchLotOnly`
- **Required variables:** `auctionId` (Int), `pageNumber` (Int, starts at 1), `pageLength` (Int)
- **Test page sizes:** Start by trying `pageLength: 500`. If API rejects or returns weirdness, fall back to 200, then 100. Document the working value.
- **Pagination loop:** Walk from page 1 until `pageNumber * pageLength >= totalCount` on first response.
- **Rate limit:** 250ms sleep between requests. Hard cap: 50 concurrent requests, but prefer sequential.

The full GraphQL query string is in the design notes provided to the orchestrator. Use it verbatim.

### Field mapping (HiBid response → output JSON)

| HiBid field | Output field | Notes |
|---|---|---|
| `id` | `id` (int) | Numeric HiBid ID, used in URL construction |
| `lotNumber` | `lot_number` (string) | Display string like "1", "1a", "42" |
| `lead` | `title` (string) | The "title" of the lot |
| `description` (raw) | `description_raw` (string) | Original HiBid description text |
| (parsed) | `description` (string) | Description with structured fields stripped out |
| (parsed from description) | `condition` (string \| null) | See condition parsing below |
| (parsed from description) | `est_retail_price` (float \| null) | If present in description |
| `featuredPicture.thumbnailLocation` | `thumb_url` (string) | Smaller thumbnail |
| `featuredPicture.fullSizeLocation` | `image_url` (string) | Full-size for expand panel |
| `pictures[].fullSizeLocation` | `additional_images` (string[]) | All other pictures |
| `lotState.highBid` | `current_bid` (float) | **Use this, NOT the top-level `bidAmount`** |
| `lotState.status` | `status` (string) | E.g., "OPEN", "CLOSED" |
| `category[0].categoryName` | `hibid_category_leaf` (string) | Leaf category |
| `category[0].fullCategory` | `hibid_category_path` (string) | Full breadcrumb |
| `lotState.timeLeftTitle` | (parsed) `close_at` (ISO 8601 string) | Parse "5/24/2026 12:00:00 PM EST" |

### Condition parsing

HiBid embeds structured info in `description` like:
```
Est. Retail Price: 55.00
Condition: BRAND NEW - SEALED
In packaging? Yes
Requires Assembly? No
Is Item Functional? Yes
Missing Major Parts? No
Is Item Damaged? No
```

Parse with regex. **Do not map conditions** — store HiBid's value verbatim,
title-cased (`BRAND NEW - SEALED` → `Brand New - Sealed`).

The five-label scheme this brief originally specified (`New` / `Like New` /
`Good` / `Fair` / `Heavily Used`) predated any real data and did not survive
contact with it. Measured over 30,358 lots, `LIKE NEW` never appears in a HiBid
listing, and half the table's inputs (`BRAND NEW`, `NEW IN BOX`, `NEW`,
`OPEN BOX`, `VERY GOOD`, `USED`, `POOR`, `DAMAGED`) never appear either. The
real vocabulary and its handling live in `scraper/condition.py`; see that
module's docstring.

| HiBid condition | Output condition |
|---|---|
| any value | that value, title-cased |
| `Select Condition Here` (unfilled dropdown) | `null` |
| no Condition line | `null` |

After parsing, set `description` to whatever free-form text remains after stripping the structured `Field: Value` lines. If nothing remains, set to empty string.

### Lot URL construction
```
https://encoreauctions.hibid.com/lot/{id}/?ref=catalog
```

### Output schema (`raw_scrape.json`)
```json
{
  "auction_id": 741675,
  "auction_name": "...",
  "scraped_at": "2026-05-21T...",
  "item_count": 14064,
  "items": [ { /* per fields above */ } ]
}
```

### CLI
```bash
python -m scraper --auction-id 741675 --output data/raw/auction_741675.json
```

---

## Build Script Specification

### Input
The categorized JSON returned by the ChatGPT Workspace Agent (Auction Agent). The Agent adds these fields to each item:
- `category` (overridden, from fixed taxonomy)
- `subcategory` (string)
- `confidence` ("low" | "medium" | "high")
- `is_bats_list` (boolean)
- `bats_buckets` (string[])
- `is_nice_pick` (boolean)
- `nice_pick_reason` (string)

### Transform
For each lot, produce a `Lot` object:

```ts
type Lot = {
  day: 'Sunday' | 'Monday' | string;  // Derived from close_at weekday
  lot_number: string;
  title: string;
  description: string;
  condition: string | null;  // HiBid's grading verbatim, e.g. 'Brand New - Open Box'
  thumb_url: string;
  image_url: string;
  lot_url: string;
  category: string;
  subcategory: string;
  is_bat: boolean;            // from is_bats_list
  bat_buckets: string[];      // from bats_buckets
  is_nice_pick: boolean;
  nice_pick_reason: string;
  confidence: 'low' | 'medium' | 'high';
};
```

### Day derivation
Parse `close_at`, get weekday name. If Sunday or Monday, use literal "Sunday"/"Monday". For other weekdays, use that name (UI handles unknown values by treating them as "Both"-eligible).

### Output
Single file: `viewer/src/data/auction_bundle.json` (or wherever the viewer imports from).

### CLI
```bash
python -m build --input data/categorized/auction_741675_categorized.json --output viewer/src/data/auction_bundle.json
```

### Validation
The script must validate output against the `Lot` shape before writing. If any item fails validation, log which item and which field, then exit with non-zero status. Do not write a partial bundle.

---

## Viewer Specification

Recreate the design handoff prototype as production code. The handoff bundle (`design_handoff_encore_lot_browser/`) is the canonical reference.

### Stack
- Vite + React 18 + TypeScript (strict mode)
- Tailwind CSS configured with the design tokens from the handoff
- `@tanstack/react-virtual` for virtualization
- `lucide-react` for icons
- Google Fonts self-hosted at build time: Newsreader, Geist, JetBrains Mono

### Required features
- **4-tab navigation**: All / Bat's List / Nice Picks / Watched
- All 3 filter controls: Day / Category / Density
- Search across `title + description + lot_number + category + subcategory`
- Card grid with virtualization at all breakpoints (the handoff specifies column counts per breakpoint)
- All card states from the handoff: default, watched, bat-flagged
- Inline expand panel (standard density) and full-row expand panel (compact density)
- Star toggle with localStorage persistence (key: `encore_watched`)
- Theme toggle: light/dark with `prefers-color-scheme` fallback on first load; persists in localStorage (key: `encore_theme`)
- Empty states per tab
- Skeleton loading states
- Condition pill renders only when `condition !== null` (graceful degradation)

### Nice Picks tab
Same structure as Bat's List tab, but filters on `is_nice_pick`. No bucket chip row (Nice Picks aren't bucket-categorized). Empty state copy distinct from Bat's List.

### Bat's List bucket chips
The chip row only renders when the "Bat's List" tab is active. Bucket list comes from the union of `bat_buckets` arrays across flagged items, sorted alphabetically with "All" first.

### Data loading
Import `auction_bundle.json` at build time (`import bundle from './data/auction_bundle.json'`). Bundle ships with the JS.

### Performance budget
- Bundle size: <500KB gzipped (excluding the data JSON)
- Time to interactive: <2s on desktop, <3s on mobile (Lighthouse)
- Smooth scroll through 14k+ items without jank

---

## Acceptance Criteria (Verification Gates)

The autonomous loop must pass **ALL** of these before declaring done:

### Scraper gates
- [ ] Runs end-to-end on auction 741675 without exceptions
- [ ] Output JSON `item_count` matches `len(items)`
- [ ] `item_count` matches `totalCount` from first GraphQL response (within ±5 for edge cases)
- [ ] 100% of items have non-empty `title`
- [ ] 100% of items have non-empty `image_url` AND `thumb_url`
- [ ] At least 80% of items have non-null `condition`
- [ ] All `lot_url` values match regex `^https://encoreauctions\.hibid\.com/lot/\d+/.*`
- [ ] No JWT, no cookie, no PII appears anywhere in committed code or logs

### Build script gates
- [ ] Runs end-to-end on a provided categorized JSON sample
- [ ] Output JSON validates against the TypeScript `Lot[]` schema (compile a small validator)
- [ ] All required Lot fields present and correctly typed for every lot
- [ ] No nulls in fields not declared as nullable

### Viewer gates
- [ ] `npm run build` succeeds with zero TypeScript errors (strict mode)
- [ ] `npm run build` succeeds with zero ESLint errors
- [ ] `npm run preview` serves the site, zero console errors on initial load with real bundle data
- [ ] Lighthouse mobile performance score ≥85 on `npm run preview`
- [ ] JS bundle (excluding data) <500KB gzipped
- [ ] All 4 tabs render and switch correctly
- [ ] Star toggle persists across page reload
- [ ] Theme toggle persists across page reload
- [ ] Cards render at all 4 breakpoints (xs, sm, md, lg) without layout breaks
- [ ] Expand panel works in both standard (inline) and compact (full-row) modes

### Test gates
3 Playwright tests, all passing against `npm run preview`:
- [ ] **search_filters**: typing in search input filters visible cards in real-time
- [ ] **star_persists**: starring a card then reloading the page shows the card remains starred
- [ ] **tab_switches**: clicking "Bat's List" tab changes the visible card set vs. "All" tab

Tests must use real selectors (data-testid attributes where helpful), no brittle text matching where avoidable.

---

## Hard Limits (Cost Ceilings)

- **Max 10 iterations per subagent** (kills the loop, not the orchestrator)
- **Max 6 hours total wall-clock time** for the entire loop
- **Max 20 files modified** per subagent in a single iteration
- **Auto-stop on Anthropic API rate limit** — don't retry, escalate to orchestrator
- **Worktree isolation**: All experimental work in disposable git worktrees. Only the final approved diff lands on the working branch.
- **No commits to main branch**. Final output is a single PR (or a single working branch ready for user to merge).

If any subagent hits its iteration cap without passing its verification gates, the orchestrator must pause and produce a status report rather than retrying indefinitely.

---

## Subagent Orchestration (suggested)

- **Orchestrator** (Opus 4.7): plans, delegates, makes integration decisions, decides when to terminate
- **Scraper builder** (Sonnet 4.6): Python scraper + tests
- **Build script builder** (Sonnet 4.6): transform module
- **Viewer builder** (Sonnet 4.6): React + Vite + TS app (this is the largest task)
- **Reviewer/Critic** (Opus 4.7): adversarial code review before integration of each subagent's output. **The reviewer must catch security issues (token leakage), reward hacking (test deletion, mocked data), and silent failures.**
- **Test runner** (Sonnet 4.6 or Haiku 4.5): mechanical — runs the suite, reports structured results
- **Documenter** (Sonnet 4.6): writes the README in plain English for a non-coder, plus the PR description

The reviewer subagent runs after each builder's iteration, not just at the end.

---

## Anti-Patterns (do NOT do)

- Do **not** store auth tokens in code, .env.example, README examples, or commit them to git
- Do **not** delete, skip, or modify Playwright tests to make them pass — fix the root cause
- Do **not** mock data or stub fields to make tests pass — fix the root cause
- Do **not** add dependencies beyond those listed in this brief without explicit orchestrator approval
- Do **not** modify `bats_list.yaml` or the design handoff files
- Do **not** implement programmatic HiBid login — token paste mode only for v1
- Do **not** include categorization logic in the codebase — categorization is external
- Do **not** assume the API requires auth without testing anon first
- Do **not** scrape lot detail pages (no per-lot HTTP requests beyond the GraphQL bulk endpoint)
- Do **not** "rewrite" the design handoff prototype's logic in dramatically different patterns just because it's prototype-grade — match design intent faithfully

---

## Deliverables

A single PR (or working branch) containing:

```
.
├── README.md                    # Operator manual: full workflow, troubleshooting
├── scraper/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry
│   ├── client.py                # GraphQL client + auth strategy
│   ├── parser.py                # Response → output JSON
│   ├── condition.py             # Condition extraction from description
│   └── tests/                   # pytest unit tests
├── build/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry
│   ├── transform.py             # categorized JSON → bundle
│   ├── schema.py                # Lot validator
│   └── tests/
├── viewer/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── index.html
│   └── src/                     # full React app
├── tests/
│   ├── playwright.config.ts
│   └── e2e/                     # 3 smoke tests
├── data/
│   ├── raw/                     # gitignored
│   └── categorized/             # gitignored, includes README explaining where these come from
├── .gitignore                   # excludes data/, .env, node_modules, dist
└── pyproject.toml               # Python deps + tooling config
```

### README must include
1. Prerequisites (Python 3.11+, Node 22+)
2. Setup steps (install deps, configure .env if needed)
3. Full weekly workflow:
   - Step 1: Run scraper (`python -m scraper --auction-id XXXXXX`)
   - Step 2: Upload raw JSON to Auction Agent in ChatGPT Enterprise, save response as `auction_XXXXXX_categorized.json` in `data/categorized/`
   - Step 3: Run build script
   - Step 4: Build viewer (`cd viewer && npm run build`)
   - Step 5: Commit + push to deploy via GitHub Pages
4. Troubleshooting: empty image URLs, auth failures, agent errors
5. How to update Bat's List (edit `bats_list.yaml`, no code changes needed)

### PR description must include
- One-paragraph plain-English summary
- List of what was built (no code, just what each piece does)
- Manual verification steps the user can run to confirm it works
- Any deferred items or known limitations

---

## Final Instructions to the Orchestrator

You are operating autonomously overnight while the user sleeps. They cannot review your code. Their only verification is behavioral: does the scraper produce a valid JSON file when run, does the viewer load and respond to interactions correctly.

**Failure modes you must guard against:**
1. **Silent token leakage** — review every committed file for secrets before integration
2. **Test deletion or stubbing** — flag any subagent attempt to modify tests
3. **Mocked data passing as real** — verify that the scraper output came from an actual API call
4. **Bundle size explosion** — virtualization is non-optional, verify it's actually wired up
5. **Image URLs missing** — this was the v1 bug; verify the gate explicitly

If you hit a verification gate you cannot pass within iteration limits, **stop and produce a clear status report** describing what works, what doesn't, and what the user should do next. Do not ship broken work to make the deadline.

End state: when the user wakes up, they should be able to:
1. Read the PR description and understand what was built
2. Run the scraper against the current week's auction
3. Upload to their Auction Agent
4. Run the build
5. See a working lot browser locally via `npm run preview`

Begin with reconnaissance: confirm anonymous GraphQL access works, then plan subagent dispatch.
