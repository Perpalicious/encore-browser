# Handoff: Encore Lot Browser — layout, density & hierarchy redesign

## Overview

A visual and layout redesign of an existing auction-lot browsing tool (React/Vite, client-side, ~20–30k lots per weekly auction). **No new features and no changed information architecture** — the tabs, filters, search, sort, category drill-down, Bat's-List bucket structure and star/watch all stay exactly as they are. What changes is card design, grid behaviour, header layout, mobile density and the colour/typographic hierarchy.

Three problems drove the work:

1. Clicking a card expanded it **inline**, stretching that grid column relative to its neighbours. → Expansion now happens in an **overlay** (right drawer on desktop, bottom sheet on mobile); the grid never reflows.
2. The header was cluttered and **scrolled out of reach**. → One 44px rail stays pinned; secondary filters live in a popover/sheet and surface as removable chips.
3. Mobile showed **1–2 lots per screen**. → A 78px list row (~9/screen) plus a 2/3/4-up card stepper (3-up ≈ 9/screen, 4-up ≈ 16/screen).

Plus a hierarchy fix: **thumb → title → condition → resale**, with retail demoted to grey and colour reserved almost entirely for condition.

## About the design files

The two files in this bundle are **design references authored in HTML** — prototypes that demonstrate the intended look and behaviour. They are **not production code to copy**. The task is to **recreate these designs inside the existing React/Vite app**, using its established component patterns, state management and build setup.

They are written as "Design Components" (`.dc.html`): a small streaming runtime wraps an HTML template plus a logic class. Ignore that wrapper entirely. What matters is:

- the **markup structure and inline styles** in the template (they map 1:1 to JSX + a style object or CSS module), and
- the **logic class** (`class Component extends DCLogic`), which is a React class component minus `render()` — `this.state`, `this.setState`, lifecycle methods and handlers all behave normally, and `renderVals()` is just the derived-values block you'd otherwise compute at the top of `render()`.

Porting is mostly mechanical: `renderVals()` → derived values/`useMemo`, `{{ x }}` → `{x}`, `<sc-for list={{ a }} as="b">` → `a.map(b => …)`, `<sc-if value={{ c }}>` → `{c && …}`, `style-hover` → a CSS `:hover` rule.

**Two porting traps found the hard way:**

- Never leave a template placeholder inside a `src`/`href` attribute — the HTML parser fetches the literal string before any JS runs. Both image slots are therefore constructed in the logic class via `React.createElement`. In real JSX this problem does not exist; write them as normal `<img>` elements.
- Persistence is wired through a `setState` override because this runtime does not forward `componentDidUpdate`. In your app, use `useEffect`/`componentDidUpdate` normally.

## Fidelity

**High-fidelity.** Colours, type, spacing, radii, motion timings and interaction behaviour are all final and should be matched precisely. The **only** placeholders are the product images: every image slot draws a neutral outlined shape on a tinted tile. Wire these to real Encore photo URLs (see *Assets*).

## Files

| File | What it is |
| --- | --- |
| `Lot Browser Prototype.dc.html` | The working prototype. 6,000 generated lots, virtualised, all filters/sort/search/keyboard/swipe/theme behaviour. **This is the implementation reference.** |
| `Lot Browser Direction.dc.html` | The design exploration that preceded it — annotated static mocks of the header rail, desktop grid, list view, both expand patterns, mobile rows, the mobile 2/3/4-up comparison, and the colour-signal legend. Useful for rationale and for the alternatives that were considered and rejected. |

Open either directly in a browser. In the prototype, resize the window below 760px to see the mobile layout.

---

## Design tokens

Defined as CSS custom properties on `:root` and `[data-theme="light"]`. Theme switching is a single attribute flip on the root element — keep that approach.

### Dark (primary)

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#0a0a0d` | App canvas, scroll area, row backgrounds |
| `--surface` | `#0f0f13` | Header, cards, drawer, sheets |
| `--s2` | `#17171d` | Inputs, inactive segmented controls, chips |
| `--s3` | `#1b1b22` | Active segment fill, figure block, toast |
| `--line` | `rgba(255,255,255,.08)` | Component borders |
| `--line2` | `rgba(255,255,255,.05)` | Row dividers, internal hairlines |
| `--text` | `#f2f0f7` | Titles, resale figures |
| `--dim` | `rgba(242,240,247,.62)` | Secondary body copy |
| `--dim2` | `rgba(242,240,247,.5)` | Inactive controls |
| `--dim3` | `rgba(242,240,247,.42)` | Retail, bucket, lot no., micro-labels |
| `--lav` | `#b3a4ff` | Primary accent: active tab, primary button, focus ring |
| `--lavt` | `#c8bcff` | Accent text on dark |
| `--lavbg` | `rgba(179,164,255,.15)` | Accent fill |
| `--lavbd` | `rgba(179,164,255,.35)` | Accent border |
| `--onlav` | `#0d0b16` | Text on a lavender fill |
| `--blusht` / `--blushbg` / `--blushbd` | `#ffb9d6` / `rgba(255,159,198,.12)` / `rgba(255,159,198,.3)` | **Active-filter chips only** |
| `--c-new` | `#7fe6bd` | Condition: New |
| `--c-like` | `#a8d4ff` | Condition: Like New |
| `--c-good` | `#cfcadd` | Condition: Good |
| `--c-fair` | `#ffcf8a` | Condition: Fair |
| `--c-heavy` | `#ff9d9d` | Condition: Heavily Used |
| `--t0` … `--t7` | `#efedf5 #f4eef2 #eef2f6 #f2f1ec #f0eef5 #f5eff1 #edf1f3 #f3f0ec` | Image-tile tints, assigned `index % 8` |
| `--ink` | `rgba(24,20,40,.16)` | Placeholder shape stroke on a tile |
| `--ink2` | `rgba(24,20,40,.45)` | Day letter / retail on a tile |
| `--plate` → `--plate0` | `rgba(248,247,252,.94)` → `rgba(248,247,252,0)` | 4-up resale gradient plate |
| `--plink` | `#16141f` | Text on the plate |
| `--sk` / `--sk2` | `rgba(255,255,255,.05)` / `.09` | Skeleton fills |
| `--ov` | `rgba(6,5,10,.66)` | Modal/drawer scrim |
| `--sh` | `0 24px 60px rgba(0,0,0,.6)` | Overlay shadow |
| personal-pick dot | `#8b6bff` (literal, both themes) | with `0 0 0 2px rgba(255,255,255,.65)` ring |
| star (watched) | `#ffd166` on tiles, `#f0a500` in rows | |

### Light (cream)

Same token names, different values:

`--bg #f6f3ec` · `--surface #fffdf8` · `--s2 #efebe1` · `--s3 #e8e3d7` · `--line rgba(28,24,20,.12)` · `--line2 rgba(28,24,20,.07)` · `--text #1b1922` · `--dim rgba(27,25,34,.76)` · `--dim2 rgba(27,25,34,.63)` · `--dim3 rgba(27,25,34,.53)` · `--lav #6b53d6` · `--lavt #5942bb` · `--lavbg rgba(107,83,214,.1)` · `--lavbd rgba(107,83,214,.3)` · `--onlav #fff` · `--blusht #c2437c` · `--blushbg rgba(217,79,140,.09)` · `--blushbd rgba(217,79,140,.28)` · `--c-new #1c8f68` · `--c-like #2a72b0` · `--c-good #6d6780` · `--c-fair #a86c11` · `--c-heavy #bd4247` · `--t0…--t7 #f1eff4 #f4eef1 #edf1f4 #f2f0ea #f0eef4 #f4eff1 #ecf0f2 #f2efe9` · `--ink rgba(24,20,40,.18)` · `--ink2 rgba(24,20,40,.5)` · `--plate rgba(255,254,250,.95)` · `--plate0 rgba(255,254,250,0)` · `--plink #1b1922` · `--sk rgba(28,24,20,.05)` · `--sk2 rgba(28,24,20,.09)` · `--ov rgba(40,34,28,.42)` · `--sh 0 24px 60px rgba(60,50,35,.22)`

The demoted tiers were deliberately raised from an earlier draft to clear ~4.5:1 (body) and ~3.4:1 (tertiary) — do not push them back down for aesthetic reasons; the app is used on a phone in a bright venue.

### Typography

Three families, loaded from Google Fonts:

- **Instrument Sans** — all UI and titles. Weights 400/500/600.
- **JetBrains Mono** — every numeric figure and every micro-label (uppercase, letter-spaced). Weights 400/500/700. Prices always carry `font-variant-numeric: tabular-nums` so columns align vertically.
- **Instrument Serif** — the wordmark only.

The old design set lot titles in an all-caps display serif; that is the single biggest reason the grid read slowly, and it should not come back.

| Role | Font | Size / weight / line-height |
| --- | --- | --- |
| Wordmark | Instrument Serif 400 | 19px / 1 |
| Wordmark sub-label | Mono 500 | 8.5px, `letter-spacing:.16em`, `--dim3` |
| Tab | Sans 500/600 | 12.5px desktop, 13px mobile |
| Search input | Sans 400 | 12.5px desktop, 13px mobile |
| Rail button | Sans 500 | 11.5px |
| Filter chip | Sans 500 | 11px |
| Card title | Sans 600 | 12.5px/1.28 desktop & 2-up · 11px 3-up · 10px 4-up · 2-line clamp |
| Card condition | Mono 500 | 8.5–9.5px, `letter-spacing:.05em`, uppercase, condition colour |
| Card resale | Mono 500 | 12.5px (11.5px at 3-up), `--text`, tabular |
| Card retail / bucket | Mono/Sans 400 | 9.5px, `--dim3` |
| List-row title | Sans 600 | 13px/1.25, single line + ellipsis |
| List-row resale | Mono 500 | 13px tabular |
| Mobile-row title | Sans 600 | 13.5px/1.28, 2-line clamp |
| Mobile-row resale | Mono 500 | 13.5px tabular |
| Section micro-label | Mono 500 | 8.5px, `letter-spacing:.13em`, `--dim3` |
| Drawer title | Sans 600 | 16px/1.3 |
| Drawer figures | Mono 500 | 17px tabular |

### Spacing, radii, motion

Spacing runs on a loose 4px rhythm; the values that matter are given per-component below.

Radii: `4–5px` micro-labels/badges · `6–8px` buttons, segments, thumbs · `9–11px` cards, inputs, sheets' inner blocks · `12–14px` popovers · `18px` sheet top corners · `20–22px` pills and toast.

Motion (all ≤180ms, all disabled under `prefers-reduced-motion`):

- `fadein` 140ms ease-out — scrims, popovers
- `slidein` 160ms ease-out — desktop drawer, from `translateX(24px)`
- `sheetup` 180ms ease-out — mobile sheets and toast, from `translateY(30px)`
- `sk` 1.4s ease-in-out infinite — skeleton opacity `.55 → 1 → .55`, staggered `(i % 6) * 90ms`

---

## The signal system

This is the core of the redesign. Enforce it — the old build's flat feel came from five colour systems competing.

| Signal | Treatment | Rule |
| --- | --- | --- |
| **Condition** | Owns the whole colour scale: a 2px full-width coloured lid under the card image, plus a mono word (grid) or dot + word (rows) | The only place the five-step palette appears |
| **Personal match** | 6–7px `#8b6bff` dot, top-left of the thumb, white ring | Was a full chip row; now costs zero layout |
| **Active filter** | Blush pill with `×` | Only ever means "you narrowed something" |
| **Money** | Greyscale, differentiated by size and weight: resale 12.5–13.5px `--text`, retail 9.5–11px `--dim3` | Never coloured. Retail's old red is gone |
| **Exceptional value** | `▲ VALUE` badge (lavender fill) on the thumb in grid; `▲` pill in rows | Top-decile resale-to-retail ratio only, computed once at load |
| **Day** | One letter (`S`/`M`) top-left on the thumb + the sticky group bar | Hide entirely when a single day is filtered |
| **Watched** | Star, amber when set | |

---

## Screens / views

### 1. Sticky header (desktop, ≥760px)

Two rows, `background: var(--surface)`, `border-bottom: 1px solid var(--line)`, `z-index: 30`.

**Row 1 — 52px, `padding: 0 16px`, `border-bottom: 1px solid var(--line2)`, `gap: 12px`.** Scrolls away is acceptable; in the prototype it is pinned with the rest.

Wordmark · tabs (`All`, `✦ Bat's List`, `Watched` + count badge; active = `--lavbg` fill, `--lavt` text, 600, `7px 13px`, radius 7px) · search field (flex, `max-width: 440px`, 34px tall, radius 9px, `--s2`, `1px solid var(--line)`, `⌕` glyph, placeholder "Search lots…   ( / )", trailing **FUZZY/EXACT** toggle: mono 9px, `letter-spacing:.1em`, `5px 7px`, radius 6px, `--lavbg`/`--lavt` when fuzzy) · then right-aligned: **jump-to-lot** field (32px, `--s2`, mono 11.5px, 62px wide, label `LOT`), **Grid | List** segmented control (2px padding, radius 8px, active pill `--s3`), theme toggle (32×32, radius 8px, `☾`/`☀`).

**Row 2 — the pinned rail, 44px, `padding: 0 16px`, `gap: 8px`.** This is the row that must never leave the viewport.

Category button (label = current sub-category, else category, else "All categories"; turns `--lavbg`/`--lavbd`/`--lavt` when set) · sort button (cycles Lot number → Resale → Retail, `⇅` glyph) · Filters button (`--lavbg` + count badge when any filter is active) · 1px × 18px divider · the active-filter chips, each removable · `CLEAR` (mono 10.5px, `--dim3`) · right-aligned count `1,204 / 24,241 LOTS` (mono 10.5px, `letter-spacing:.08em`, `--dim3`).

Rationale: everything in the old header that was *state* is now a chip, and everything that was *a control* is behind one of three buttons. Nothing is hidden — you can always see what you filtered.

### 2. Sticky group bar

A 7px/14px strip below the header, `background: var(--bg)`, `border-bottom: 1px solid var(--line2)`, `z-index: 10`. Shows the day and lot range currently on screen — `SUNDAY · S-1204 → S-1261` — derived from the first and last visible virtualised items, so it updates as you scroll. On mobile it also carries the **Rows | Cards** toggle and the **2 / 3 / 4** stepper (right-aligned, 22px-wide segments).

### 3. Desktop grid

`display: grid`, `gap: 12px`, `padding: 0 16px`. Column count is computed, not breakpointed:

```
cols = clamp(2, MAX, floor((containerWidth - 32 + 12) / (196 + 12)))
colW = (containerWidth - 32 - 12 * (cols - 1)) / cols
rowH = colW + 2 + 63 + 12          // image + lid + text block + gap
```

> **Deviation from this spec, decided 2026-08-08.** The spec's ceiling of 9 is
> too high for a wide monitor: at 2140px it laid out 9 columns and the cards
> got too small to scan. `MAX` is now per-density — **6** in standard, **8** in
> compact — so a wider window gives bigger cards rather than more of them, and
> the density toggle still buys real extra density. See `maxCols()` in
> `viewer/src/hooks/useGridGeometry.ts`, asserted in its unit test.

≈ 6 columns and ~30 lots visible at 1440×900.

**Card** — radius 11px, `background: var(--surface)`, `1px solid var(--line)`, `overflow: hidden`, whole card is the click target (the old per-card "Details" button is gone), hover → `border-color: var(--lavbd)`, keyboard cursor → `border-color: var(--lav)` + `box-shadow: 0 0 0 2px var(--lavbd)`.

1. **Image tile** — `aspect-ratio: 1/1`, `background: var(--t{i%8})`, flex-centred, padding `16px` (`11px` under 150px wide, `8px` under 100px). The image is `object-fit: contain; max-width:100%; max-height:100%`. A near-white tile is deliberate: Encore's product shots are mostly white-background cut-outs, so they blend into the tile instead of floating in a black box, and nothing is ever cropped. Fallback when there is no image: a 56%×56% rounded-rect outline in `--ink` with a small centred dot.
   - Day letter: mono 700 8px `--ink2`, top-left `5px/6px`.
   - Personal-pick dot: 6px `#8b6bff`, top `5px` left `20px`.
   - `▲ VALUE` badge: bottom-left, mono 700 8.5px, white on `#8b6bff`, `3px 5px`, radius 4px.
   - Star: 26×26, top-right `4px`, radius 8px, `rgba(14,12,22,.45)` + `backdrop-filter: blur(6px)`; stops propagation.
2. **Condition lid** — a 2px full-width bar in the condition colour.
3. **Text block** — `padding: 8px 9px 9px`, `gap: 4px`: title (2-line clamp, `min-height: 33px`, `text-wrap: pretty`) · row of `CONDITION` ↔ `$resale` · row of `bucket` ↔ `$retail` (the second row is dropped at 3-up and 4-up).

### 4. Desktop list view

One row per lot, 67px, `padding: 7px 10px`, `border-bottom: 1px solid var(--line2)`, hover `--lavbg`.

Columns, left to right: 52×52 thumb (radius 8px, tint, pick dot) · flexible title + bucket sub-line · 110px condition (dot + mono word) · 52px value tick · 78px resale (right-aligned, mono 13px tabular) · 66px retail (`--dim3`) · 56px lot number · 34px star.

Column headers double as the sort control; the active sort column is `--lavt` with a `↓`.

### 5. Mobile (<760px)

**Header** — 8px/12px padding: search field (36px) + Filters button (36px, count badge) + theme toggle (36×36) on one line; tabs and the result count below.

**Rows mode (default) — 78px.** `padding: 9px 13px`, `gap: 11px`: 58×58 thumb · title (2-line clamp, 13.5px) over a meta line (condition dot + word, lot no., value tick) · right-aligned resale over retail · 26px star. ~9 lots per screen.

**Cards mode** — same card as desktop at 2, 3 or 4 columns; gap `10 / 8 / 6px`, text block `8px 9px 9px` / `6px 7px 7px` / `5px 6px 6px`, text-block height `63 / 48 / 33px`.

- **3-up (recommended default)** — ~9 lots/screen, 113px tap targets, title survives at 11px over two lines; the bucket line is dropped.
- **4-up** — ~16 lots/screen. The title can no longer carry the lot, so the photo does: resale and retail move **onto** the image in a bottom gradient plate (`linear-gradient(to top, var(--plate), var(--plate0))`, `padding: 10px 5px 3px`, resale mono 700 10.5px `--plink`, retail mono 500 8px `--ink2`), and the value tick is suppressed. Titles at 10px are near the legibility floor — keep it as an option, not a default.
- **2-up** — ~4 lots/screen; the only mode that keeps the bucket line.

### 6. Detail overlay — the fix for the inline-expand problem

Never expand inside the grid. The overlay is:

- **Desktop** — right drawer, `position: fixed; top:0; right:0; bottom:0; width: 430px`, `border-left: 1px solid var(--line)`, `slidein` 160ms. The grid keeps its scroll position and stays visible, so you can step through candidates.
- **Mobile** — bottom sheet, `left:0; right:0; bottom:0; height: 88vh`, `border-radius: 18px 18px 0 0`, `sheetup` 180ms.

Both sit above a `--ov` scrim (`fadein` 140ms) that closes on click; `Escape` also closes.

Contents, top to bottom: title (16px/1.3) + close button (28×28, `--s2`) · 4:3 image tile (radius 11px) · meta line (condition dot + word, `SUNDAY · LOT S-1`, `▲ TOP-DECILE SPREAD` badge if applicable) · figure block (`--s2`, radius 10px: `RESALE $25–40` and `RETAIL $72` in mono 17px, with confidence and outlook pills right-aligned — confidence green/blue/grey for High/Medium/Low, outlook green/amber/red) · CATEGORY / SUB / BUCKET rows (66px mono labels) · the resale note · the personal-pick block when present (`rgba(139,107,255,.1)` on `rgba(139,107,255,.22)`, mono 9px `PERSONAL PICK · STRONG MATCH` header, 11.5px/1.55 body) · footer: **View on Encore ↗** (flex, `--lav` fill, `--onlav` text, 12.5px 600), watch toggle, and `‹` `›` to step to the previous/next lot **without closing**.

### 7. Filters overlay

Desktop: popover, `top: 100px; right: 16px; width: 420px; max-height: 78vh`, radius 14px. Mobile: bottom sheet, `max-height: 86vh`, radius 18px top.

Sections, each with a mono 8.5px `letter-spacing:.13em` `--dim3` label: **CONDITION** (5 wrapping chips, 44px tall — `9px 13px`, radius 9px; selected = `--lavbg`/`--lavbd`/`--lavt`) · **RESALE CONFIDENCE** (All / Med+ / High segmented) · **OUTLOOK** (All / Poor / Fair / Good / Strong) · **DAY** (Sun / Mon / Both) beside **SORT** · a row of `♥ Personal picks` and `↗ Potential resales` toggles (blush when on) · a full-width primary **Show 1,204 lots** button.

Every target is ≥44px so the sheet is usable one-handed.

### 8. Category drill-down

Two-pane popover anchored under the rail (`left: 16px; top: 104px`), each pane 210px, scrollable, `max-height: 60vh`. Left = categories with counts; right = sub-categories of the selection. Picking a sub-category closes the popover. "All categories" clears both.

### 9. Bat's List empty state

When the tab is active but no bucket is chosen: centred column — 46px lavender rounded-square mark, "Pick a bucket", one line of help, then the **groups** as cards (name + `N LOTS`, min-width 150px), and once a group is chosen its **buckets** as pills below a hairline. This preserves the existing two-level group → bucket structure while replacing the native `<select>`.

### 10. Loading, empty, toast

- **Skeletons** — shaped to the **current view**, not a fixed card: in grid/card modes an `aspect-ratio: 1/1` block plus two text bars; in list/rows modes a `rowH`-tall row with a 52px (desktop) or 58px (mobile) square and two bars. The count is `ceil(viewportH / rowH)` (+ a row of slack, capped at 36 cards) rather than a constant, so the placeholder always fills exactly one screen. Because view mode is persisted, a user who works in List must not be shown card skeletons — that reads as a broken page. 480ms in the prototype; in production, show them until the lot index is parsed.
- **Empty** — "No lots match", one line of help, and a **Clear filters** button.
- **Toast** — centred, 26px from the bottom, radius 22px, `--s3`, 1.5s: "Added to list" / "Hidden" / "Lot not in current results".

---

## Interactions & behaviour

### Input mode vs. layout mode

Layout is chosen by **width** (`<760px` = mobile), but affordances are chosen by **input**: `matchMedia('(pointer: coarse)')`, re-evaluated on change. This matters mainly for tablets — an iPad is 768–1366pt, so it gets the desktop grid (which auto-computes 3–4 columns in portrait, 5–6 in landscape) but must not inherit desktop interaction assumptions.

When the pointer is coarse:

- **Swipe triage is enabled on desktop list rows**, using the same shell and ±70px thresholds as mobile rows.
- **List rows grow to 78px** (from 67px) with `11px 12px` padding.
- **Star hit areas grow to 44×44** (from 34px, 13px glyph → 16px).
- **The detail panel and filters render as bottom sheets** rather than a side drawer / anchored popover.
- **The header hint line** switches from the keyboard map to `SWIPE → WATCH` (no hide — see the deviation note under "Swipe triage").

No stepper is offered on tablet: 4-up on a 1024pt iPad is roughly the same physical card size as 3-up on a phone, so the computed column count is already right.

Note the swipe shell requires an opaque row background (`var(--bg)`, or `var(--lavbg)` under the keyboard cursor) so the action layer beneath stays hidden until the row translates.

### Keyboard (desktop)

Lot order runs left-to-right, and the keys follow that:

| Key | Action |
| --- | --- |
| `→` / `←` (or `l` / `h`) | Next / previous lot, sequential — wraps across rows |
| `↓` / `↑` (or `j` / `k`) | Down / up one row (± column count) |
| `Space` / `Enter` | Open the detail overlay for the cursor lot |
| `w` | Watch / unwatch the cursor lot |
| `f` | Toggle the filters overlay |
| `/` | Focus search |
| `Escape` | Close any overlay; blur the search field |

The cursor is a visible ring on the card. Moving it scrolls the container by direct `scrollTop` arithmetic (`row * rowH`, clamped to the viewport) — **not** `scrollIntoView`. While the detail overlay is open, arrow movement also advances the overlay.

### Swipe triage (mobile rows)

Pointer events on the row; the row translates on X up to +140px over a fixed action layer. Past **+70px** → watch (row background `--lavbg`, `★ WATCH` revealed left; `☆ REMOVE` when the lot is already watched, since the same gesture is the undo). Release below threshold snaps back. `touch-action: pan-y` keeps vertical scrolling intact. Each commit fires a toast.

> **Deviation from this spec, decided 2026-08-01.** The spec's second gesture — swipe **left** past −70px to hide the lot from the results — was implemented, used, and then removed. Dropping lots out of the result set on a flick is too destructive for a gesture that easy to make by accident while scrolling a phone one-handed at a venue. There is now exactly one swipe, it is rightward, and it toggles. A left drag does not move the row at all, so nothing suggests an action is hiding over there. Do not reinstate it without a deliberate decision; `tests/e2e/keyboard_and_triage.spec.ts` asserts a left swipe is inert.

This is what makes "Watched" useful for this team: it is a shortlist you build while scanning, not a bid tracker (bids are tracked on Encore itself).

### Virtualisation

Uniform row heights make this cheap:

```
totalRows = ceil(filtered.length / cols)
first     = max(0, floor(scrollTop / rowH) - 2)
last      = min(totalRows, ceil((scrollTop + viewportH) / rowH) + 2)
```

A spacer div of `totalRows * rowH` establishes the scrollbar; the grid is absolutely positioned at `top: first * rowH`. Only `(last - first) * cols` cards exist in the DOM. Scroll state updates only when it moves >4px. The container is measured with a `ResizeObserver` plus a window `resize` listener.

If titles ever wrap to three lines, this assumption breaks: the spacer height and the window's `top` offset both derive from `rowH × n`, so variable-height cards drift out of sync with the scrollbar. Keep the 2-line clamp (the full title is always in the drawer). If you ever need three lines, make **every** card taller — raise the title `min-height` and the `rowH` constant together — rather than letting heights vary; genuinely variable heights require measured virtualisation.

### Filtering & sorting

One pass over the array, short-circuiting in this order: hidden → tab → day → category → sub-category → condition → confidence → outlook → personal picks → potential resales → search. The result is memoised against a joined key of every filter value, so re-renders during scroll never re-filter.

Sort: lot number (natural array order), resale desc, retail desc.

**Search.** Each lot precomputes a lowercased title and a token array (split on non-alphanumerics) at parse time. *Exact* is a plain substring test. *Fuzzy* is a scored, token-AND match — **every** query token must match something, or the lot is rejected:

| Match | Score |
| --- | --- |
| Whole query as a substring of the title | `1200 − position` (capped at 200) |
| Token equals a title word | `100 − wordIndex` |
| Token is a word **prefix** | `70 − wordIndex` |
| Token (≥4 chars) appears mid-word | `30` |
| Numeric token appears anywhere in a word | `60` |
| Single token (≥4 chars), subsequence of the title | `4` — last resort |

Numeric tokens (`42151`, `18v`) never match by prefix or subsequence, so model numbers stay strict. When a query is active and the sort is the default "Lot number", results are ranked by **relevance** (score desc, then lot order); an explicit Resale or Retail sort still wins. Scores are stashed on the record during the filter pass, so ranking costs nothing extra.

### Persistence

Debounced 350ms after any state change. Tab, query, fuzzy flag, category, sub-category, sort, conditions, confidence, outlook, picks, resales, day, view, mobile view, columns, theme, group and bucket go to **both** `localStorage['encore.lotbrowser.v1']` and the URL hash (`#s=<encoded JSON>`). Watched, hidden and scroll position go to localStorage only. On load the hash wins over localStorage, so a filtered view is shareable; scroll position is restored one frame after the skeletons clear.

### Accessibility

`:focus-visible` → `2px solid var(--lav)`, `outline-offset: 2px`. Star buttons carry `aria-label` ("Add to list: <title>") and `aria-pressed`. A visually hidden `aria-live="polite"` region announces the result count. All animation is disabled under `prefers-reduced-motion: reduce`.

---

## State

```
tab            'all' | 'bats' | 'watched'
q, fuzzy       search string, boolean
cat, sub       string | null          hierarchical category drill-down
sort           'lot' | 'resale' | 'retail'
conds          string[]               multi-select condition
conf           'all' | 'med' | 'high'
out            'all' | 'Poor' | 'Fair' | 'Good' | 'Strong'
picks, resales boolean                personal-match, top-decile
day            'sun' | 'mon' | 'both'
view           'grid' | 'list'        desktop
mView, cols    'rows' | 'cards', 2|3|4   mobile
theme          'dark' | 'light'
group, bucket  string | null          Bat's List two-level selection
watched,hidden { [lotId]: 1 }
sel, cursor    index into the filtered array (-1 = closed)
filtersOpen, catOpen, loading, toast
scrollTop, vh, vw, swipeId, swipeDx
```

Derived per render: the filtered+sorted array (memoised), the geometry object (`cols`, `colW`, `rowH`, `gap`, `padX`, `mode`), and the visible window.

## Data shape

The prototype generates lots deterministically; your real records need these fields:

```
{ i, title, cat, sub, bucket|null, retail, lo, hi, mid,
  cond: 'New'|'Like New'|'Good'|'Fair'|'Heavily Used',
  day: 'S'|'M', lot: 'S-1204',
  conf: 'Low'|'Medium'|'High',
  out:  'Poor'|'Fair'|'Good'|'Strong',
  pick: boolean, note, match, img: url|null,
  ratio: mid / retail, tick: ratio >= p90(ratio)   // computed once at load
}
```

`tick` is the 90th-percentile threshold over the whole set, computed once after parsing — not per filter result.

## Assets

**None shipped.** Every image is a placeholder: a tinted tile with an outlined rounded-rect and dot in `--ink`.

To wire real photos, set `img` on each lot and render `<img src={lot.img} loading="lazy" decoding="async" style={{maxWidth:'100%',maxHeight:'100%',objectFit:'contain',display:'block'}} onError={…} />` inside the tile, falling back to the drawn shape on error or when `img` is null. Because the tile owns the framing and the image is always `contain`-fitted and flex-centred, the off-centre crops in the current build cannot recur.

Icons are text glyphs (`⌕ ☆ ★ ✦ ✕ ‹ › ⌄ ⇅ ↗ ♥ ▲ ☾ ☀`). Swap them for the icon set already in your codebase; sizes are given per component above.

Fonts: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts. Self-host them — this app is used on venue wifi.
