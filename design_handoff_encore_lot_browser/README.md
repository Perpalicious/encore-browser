# Handoff: Encore Lot Browser

A personal-use replacement UI for browsing weekly auction lots from Encore Auctions (HiBid platform). The official site is slow and hard to filter; this design replaces it with a fast, shopping-app-style browser optimized for one user on iPhone (primary) and MacBook Air (secondary).

---

## About the Design Files

The files in this bundle are **design references created in HTML/React-via-Babel** — clickable prototypes showing intended look, layout, and behavior. They are **not** intended to ship as-is.

Your task is to **recreate these designs in the target codebase's existing environment** (React, Next.js, Vue, SwiftUI, etc.) using its established patterns and component libraries. If no environment exists yet, choose the most appropriate framework for the project (React + Vite + Tailwind is a fine default) and implement there.

The HTML files use:
- Tailwind CSS (CDN) — port to the codebase's existing utility/CSS approach
- Inline lucide-style icons — replace with `lucide-react` (or the codebase's icon set)
- Babel standalone for in-browser JSX — replace with the codebase's normal build pipeline
- Three Google Fonts: **Newsreader** (display serif), **Geist** (sans body), **JetBrains Mono** (numeric/metadata)

---

## Fidelity

**High-fidelity.** The mocks are intended as pixel-perfect reference: final colors, typography, spacing, dark mode, interactions, and animation timing are all set. Recreate the UI faithfully using the target codebase's existing patterns. Where the codebase already has a button/input/pill primitive that matches the visual, use that — the goal is fidelity to the design *intent*, not literal markup copy.

---

## Screens / Views

There is **one screen**: the lot browser. It is fully responsive. Below, each component is documented.

### Sticky Header

The sticky header has two distinct layouts: **mobile** (<768px) and **desktop** (≥768px). Both are anchored top with backdrop-blur and a hairline bottom border.

#### Mobile header (≤767px) — 3 rows max

Row 1 — `pt-2.5 pb-2`, all controls 40px high (`h-10`):
- **Search input** (flex-1): pill, `rounded-full`, `bg-white` / `dark:bg-night2`, ring-1 hairline, leading search icon, trailing X clear button when content present, placeholder "Search lots...".
- **Filters button** (40×40, circular): `SlidersHorizontal` icon. When the disclosure is open OR any non-default filter is active, the button background turns to `bg-ink` / `dark:bg-bone`. A small ember-colored numeric badge (top-right) shows count of active non-default filters (day/category/density).
- **Theme toggle** (40×40, circular): Sun/Moon icon, neutral chrome.

Row 2 — tabs + count, no extra vertical padding:
- **Tabs**: `All` / `Bat's List` (with leading ember sparkle) / `Watched` (with numeric badge). 44px tap height. Active tab uses `text-ink`/`text-bone` + 2px ember underline; inactive uses secondary text.
- **Count**: right-aligned, `11px` mono uppercase, format `N/M`.

Row 3 — only when Filters button toggled open. Animates open via `grid-template-rows: 0fr → 1fr` (320ms `cubic-bezier(.2,.7,.2,1)`). Contains three `FilterFieldRow`s (label + control):
- **Day**: segmented pill (Sunday / Monday / Both), full-width.
- **Category**: native `<select>` styled as a pill.
- **Density**: segmented pill (Standard / Compact), full-width.

#### Desktop header (≥768px) — 2 rows

Row 1 — `pt-3 pb-2.5`, gap-3:
- **Wordmark**: `Encore` (Newsreader italic, 22px) + `LOT BROWSER` (mono, 10px, 0.22em tracking) — left-aligned, click is a no-op anchor.
- **Search input** (flex-1, max-w-xl): same styling as mobile, 40px.
- **Day segmented pill** (34px tall): Sunday / Monday / Both.
- **Category select** (40px tall): pill with chevron.
- **Density segmented pill** (34px tall): Standard / Compact.
- **Theme toggle** (40×40 circular).

Row 2 — tabs + count, same as mobile.

#### Bat-bucket chip row (both layouts)

Appears as a 4th row only when the **Bat's List** tab is active. Animates in (fade + 4px slide). Horizontally scrollable, no scrollbar. Each chip is `h-9 px-3.5 rounded-full text-[13px] font-medium`. Active chip is `bg-ink text-paper` (inverted in dark); inactive is `bg-white ring-1 ring-rule`. An "All" chip clears the bucket filter. Selected non-"All" chips show a leading `Check` icon. Single-select.

### Sticky-header height budget

Mobile, header collapsed: **~104–110px** (~12–13% of an iPhone 14 viewport, ~33% of header budget per the spec). Mobile, with filters open: **~250px**. Adding the Bat bucket chip row adds ~52px on top.

---

### Card Grid

`grid gap-4 md:gap-5`. Column counts:
| Breakpoint | Standard | Compact |
|---|---|---|
| <640px       | 1 | 2 |
| 640–1023px   | 2 | 3 |
| 1024–1279px  | 3 | 4 |
| ≥1280px      | 4 | 5 |

The container max-width is `1480px`, padded `px-4 md:px-6`, with `pt-4 md:pt-6 pb-24`.

### Lot Card

Container:
- `rounded-2xl bg-white dark:bg-night2 ring-1 ring-rule/60 dark:ring-dusk shadow-card overflow-hidden`
- Hover: `-translate-y-[1px]` + `shadow-cardHover` (200ms)
- `is_bat === true`: ring tints to `ring-ember/35` AND a 3px ember left stripe (`absolute left-0 inset-y-0 w-[3px] bg-ember/80`)
- `watched === true`: ring tints to `ring-ember/60`

Anatomy (top → bottom):
1. **Thumbnail** (`aspect-[4/3]` standard, `aspect-[5/4]` compact). `object-cover`. Backed by `bg-paper2 dark:bg-coal` so empty space matches.
   - **Loading**: shimmer overlay (1.6s linear infinite gradient sweep, `200% background-size`).
   - **Broken / missing**: centered `ImageOff` icon (28px, stroke 1.5) + `NO IMAGE` mono caption underneath.
2. **Star button** (top-right of thumbnail, 44×44, circular, backdrop-blur):
   - Unwatched: `bg-white/85 ring-1 ring-black/5 text-ink/80`, outline star.
   - Watched: `bg-ember text-white shadow-pop`, filled star.
   - Always stops event propagation. Star tap **never** expands.
3. **Watched pill** (bottom-left of thumbnail, only when watched): "WATCHING" ember pill, `text-[10px] uppercase tracking-[0.14em] px-2 py-1 rounded-full bg-ember text-white shadow`.
4. **Body** — `px-4 pt-3.5 pb-4` (standard), `px-4 pt-2.5 pb-2.5` (compact).
   - **Meta row** (flex justify-between, mb-1.5): **Condition pill** on the left, **Day badge** on the right.
     - Condition pill: 11px uppercase, `tracking-wide font-medium px-2 py-[3px] rounded-full ring-1`. See **Design Tokens → Condition colors**.
     - Day badge: 10px uppercase 0.14em mono-ish, leading 1.5×1.5px dot — ember for Sunday, indigo-500 for Monday.
   - **Title** (Newsreader, 17px/1.22 standard or 15px/1.25 compact, `text-ink dark:text-bone`). Clamped to 2 lines via `-webkit-line-clamp:2`. `min-height: 2.45em` (2.5em compact) so card heights stay aligned even with single-line titles.
   - **Bottom row** (`mt-3` standard, `mt-2` compact, flex gap-1.5 wrap):
     - **Bat bucket pill** (only when `is_bat`): leading Sparkle (11px), first bucket label, and `+N` if more buckets exist. Style: `bg-ember/10 text-ember2 ring-1 ring-ember/20` in light, `bg-ember/15 text-ember dark:ring-ember/30` in dark. If `is_bat` is true but `bat_buckets` is empty, show pill labeled "Match".
     - **Details toggle** (ml-auto): pill containing label + chevron. Collapsed: `bg-paper2 text-ink ring-1 ring-rule/60`, label "Details", `ChevronDown`. Expanded: `bg-ink text-paper`, label "Hide", `ChevronUp`. Heights: 32px standard, 28px compact. Stops propagation but ALSO calls onToggleExpand; the card body also toggles expand on tap (the toggle is a redundant visible affordance).
5. **Expanded panel** — two modes:
   - **Standard density (inline)**: rendered inside the card. Top border, larger image, full description, category/sub/buckets `<dl>`, then a row with primary CTA `View on Encore` (ember pill, 44px) + `Collapse` text button.
   - **Compact density (full-row)**: rendered as a **sibling grid item with `col-span-full`**, inserted into the grid immediately after the row containing the expanded card. Layout is `grid md:grid-cols-[1fr_1.1fr] gap-5 md:gap-7 p-5 md:p-6` — image left, content right on desktop; stacked on mobile. Includes the same `View on Encore` CTA, an X close icon in the top-right, and a redundant "Collapse" text button.
   - Both modes hide the lot number on the card front and surface it inside the expand panel as a mono chip alongside condition + day.

### Tab Button

`relative inline-flex h-11 px-3 md:px-4 text-[14px] md:text-[15px] font-medium`. Active state: `text-ink dark:text-bone` + 2px ember underline pinned to `-bottom-px left-2 right-2 rounded-full`. Inactive: secondary text with hover to primary. Badge (numeric): `min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-semibold tabular-nums`. Badge background: `bg-ember text-white` when active tab, `bg-paper2 dark:bg-coal` otherwise. Optional leading ember sparkle (for Bat's List).

### Skeleton Card

Same overall shape as a card. Image area + meta + title placeholders all use the shimmer treatment. Shown for 900ms on initial mount via `setTimeout` (placeholder for real data fetching).

### Empty State

Centered, max-width `28rem`, `py-20 md:py-28`. Circular ember-tinted icon badge (Sparkle, 24px), Newsreader 26px headline, secondary text body, optional **Clear filters** ember pill button (omitted on the Watched tab — instead the body copy tells the user to star a card).

---

## Interactions & Behavior

| Trigger | Effect |
|---|---|
| Tap card body (anywhere except star, details toggle, or in-panel CTA) | Toggles expand for that lot. Other expanded cards remain expanded. |
| Tap Details toggle | Same as card body tap. Provides a visible affordance. |
| Tap star | Toggles `watched` for that lot. Never expands. Never collapses any other card. |
| Switch tab | View changes immediately; expand state persists per lot. |
| Switch day / category / density | Filters apply immediately. |
| Type in search | Filters by `title`, `description`, `lot_number`, `category`, `subcategory` (case-insensitive `includes`). |
| Tab → Bat's List | Bucket chip row slides down. Default bucket selection is "All". |
| Tab → Watched | Filters to watched lots **ignoring** day/category. Bucket row hidden. |
| Mobile Filters icon | Toggles disclosure animation (320ms grid-template-rows). |
| Theme toggle | Toggles `class="dark"` on `<html>`. First load reads `prefers-color-scheme`. |

### Sort

Default sort, applied after filtering:
1. `is_bat === true` first
2. then `day === "Sunday"` before `"Monday"`
3. then `lot_number` ascending (string compare)

### Animations

- **Expand panel (standard, inline)**: `grid-template-rows: 0fr → 1fr` over 320ms `cubic-bezier(.2,.7,.2,1)`. Inner uses `overflow: hidden`. Respects `prefers-reduced-motion` (disabled).
- **Expand panel (compact, full-row)**: fades in 280ms ease-out (`animate-fadeIn`).
- **Bucket chip row entry**: 220ms slideDown (4px translate + fade).
- **Card hover**: `-translate-y-[1px]` + shadow swap, 200ms.
- **Shimmer**: 1.6s linear infinite.

---

## State Management

All state lives in the root component via `useState`:

| State | Type | Default |
|---|---|---|
| `dark` | boolean | matches `prefers-color-scheme` |
| `query` | string | `''` |
| `dayFilter` | `'Sunday' \| 'Monday' \| 'Both'` | `'Both'` |
| `category` | string | `'All'` |
| `density` | `'standard' \| 'compact'` | `'standard'` |
| `tab` | `'all' \| 'bat' \| 'watched'` | `'all'` |
| `batBucket` | string | `'All'` |
| `expandedIds` | `Set<string>` (lot_number) | `new Set()` |
| `watched` | `Set<string>` (lot_number) | `new Set()` |
| `loading` | boolean | `true` → false after 900ms |
| `mobileFiltersOpen` | boolean | `false` |

A `useColumns(density)` hook returns the current column count by reading `window.innerWidth` against Tailwind's `sm/lg/xl` breakpoints; used to chunk filtered lots into row-aware groups so the full-row expand panel can be inserted at the right position in Compact mode.

### Data fetching (for production)

In this prototype the data is a hard-coded array of ~18 mock lots. In production the component should accept lots as a prop (or fetch via an injected query). Scale target: **~18,000 lots/week**. The card grid must be virtualized (e.g., `react-virtuoso` masonry or `@tanstack/react-virtual` with row chunking) — the prototype renders all cards directly, which won't survive at scale.

---

## Design Tokens

### Colors

Defined as Tailwind colors in `index.html` (`tailwind.config.theme.extend.colors`).

**Light (warm editorial / paper)**
| Token | Hex | Use |
|---|---|---|
| `paper`  | `#FAF6EE` | page background |
| `paper2` | `#F3ECDD` | surface, neutral chips |
| `ink`    | `#1A1612` | primary text |
| `ink2`   | `#544A3D` | secondary text |
| `rule`   | `#E6DDC8` | hairline borders |
| `ember`  | `#B6502A` | accent (primary CTA, watched, sparkle, focus ring) |
| `ember2` | `#8B3A1A` | accent — hover/active variant |

**Dark (charcoal)**
| Token | Hex | Use |
|---|---|---|
| `night`  | `#0F1012` | page background |
| `night2` | `#17181B` | surface (card, input, select) |
| `coal`   | `#1F2024` | surface-2 (chips, segmented track) |
| `bone`   | `#ECEDEF` | primary text |
| `bone2`  | `#A0A2A8` | secondary text |
| `dusk`   | `#2A2C31` | hairline borders |

Ember is shared between modes; only its supporting tints (`/10`, `/15`, `/20`, `/30`) change.

**Condition pill colors** (Tailwind utility classes — keep faithful to these tints):
| Condition | Light | Dark |
|---|---|---|
| New, Like New | `bg-emerald-50 text-emerald-800 ring-emerald-200` | `bg-emerald-500/15 text-emerald-300 ring-emerald-500/30` |
| Good | `bg-paper2 text-ink2 ring-rule` | `bg-coal text-bone2 ring-dusk` |
| Fair | `bg-amber-50 text-amber-800 ring-amber-200` | `bg-amber-500/15 text-amber-300 ring-amber-500/30` |
| Heavily Used | `bg-rose-50 text-rose-800 ring-rose-200` | `bg-rose-500/15 text-rose-300 ring-rose-500/30` |

### Typography

| Family | Use |
|---|---|
| **Newsreader** (Google Fonts, opsz 6–72, wt 400/500/600) | Card titles, headlines, wordmark, empty-state title |
| **Geist** (Google Fonts, 400/500/600/700) | UI body — buttons, inputs, secondary text, descriptions |
| **JetBrains Mono** (400/500) | Lot numbers, count "N/M", `data-screen-label`-style chips, uppercase eyebrow metadata |

Body font-feature-settings: `'ss01', 'cv11'`. Serif font-feature-settings: `'liga', 'kern'` with `letter-spacing: -0.01em`.

| Element | Family | Size / line-height |
|---|---|---|
| Card title (standard) | Newsreader | 17px / 1.22 |
| Card title (compact)  | Newsreader | 15px / 1.25 |
| Expand panel title (full-row) | Newsreader | 22–26px / 1.15 |
| Expand panel title (inline)   | Newsreader | 18px / 1.2 |
| Empty state headline  | Newsreader | 26px |
| Body / description    | Geist     | 14–14.5px / 1.55–1.6 |
| Tab label             | Geist 500 | 14–15px |
| Filter pill label     | Geist 500 | 13px |
| Condition pill        | Geist 500 uppercase | 11px (10px when `size="sm"`) |
| Day badge / eyebrow   | Geist 500 uppercase | 10px, tracking 0.14em |
| Count text            | JetBrains Mono | 11–12px uppercase, tracking 0.12–0.14em |
| Lot number chip       | JetBrains Mono | 11px |

### Spacing & radius

- Page padding: `px-4` mobile, `px-6` desktop. Vertical: `pt-4 md:pt-6 pb-24`.
- Grid gap: `gap-4 md:gap-5` (16/20px).
- Card: `rounded-2xl` (16px). Inputs/buttons: `rounded-full` (pill).
- Hairline: 1px solid `rule` / `dusk`.
- Tap targets: **never below 44px** for primary actions (search, theme, star, tabs, CTA). 34–40px for dense desktop chrome.

### Shadows (defined in tailwind config)

| Token | Definition |
|---|---|
| `shadow-card`      | `0 1px 0 rgba(26,22,18,.04), 0 1px 2px rgba(26,22,18,.04), 0 4px 12px -2px rgba(26,22,18,.06)` |
| `shadow-cardHover` | `0 1px 0 rgba(26,22,18,.05), 0 8px 24px -6px rgba(26,22,18,.14)` |
| `shadow-cardDark`  | `0 1px 0 rgba(0,0,0,.4), 0 4px 12px -2px rgba(0,0,0,.4)` |
| `shadow-pop`       | `0 12px 40px -10px rgba(26,22,18,.25)` (used on watched star) |

### Focus

Custom outlines (warm, never blue): `2px solid #B6502A` light, `#D87B57` dark, `outline-offset: 2px`, `border-radius: 4px`. Apply only on `:focus-visible`.

---

## Data Shape

Each lot:

```ts
type Lot = {
  day: 'Sunday' | 'Monday';
  lot_number: string;       // e.g. '0142'
  title: string;            // often awkwardly written by auction staff
  description: string;      // may be empty or 'As shown.'
  condition: 'New' | 'Like New' | 'Good' | 'Fair' | 'Heavily Used';
  thumb_url: string;        // may be ''  → render broken-image fallback
  image_url: string;        // larger, for expand
  lot_url: string;          // opens in new tab
  category: string;
  subcategory: string;
  is_bat: boolean;
  bat_buckets: string[];    // may be [] even when is_bat is true
};
```

`is_bat` is the **authoritative** flag for whether to apply Bat's-List visual treatment. `bat_buckets` is purely informational and may be empty.

---

## Constraints — must NOT include

- ❌ No bid amounts, prices, or pricing language
- ❌ No countdown timers, "ending soon", or auction urgency UI
- ❌ No Encore branding/promo content
- ❌ No ads
- ❌ No share buttons
- ❌ No login / account / profile UI

---

## Assets

- **Fonts**: Newsreader, Geist, JetBrains Mono — all from Google Fonts. Self-host in production.
- **Icons**: prototype uses hand-rolled lucide-style SVGs. In production, install `lucide-react` and use: `Star`, `Search`, `X`, `Sun`, `Moon`, `ChevronDown`, `ChevronUp`, `ExternalLink`, `ImageOff`, `SlidersHorizontal`, `Check`, and a Sparkle (lucide has `Sparkles` — single-sparkle variant is fine).
- **Images**: prototype uses `picsum.photos` seeded URLs. In production, lots come from the Encore scrape; treat `thumb_url`/`image_url` as untrusted and always render the broken-image fallback on error.

---

## Files

Bundled in this folder for reference:

| File | What it contains |
|---|---|
| `index.html`    | HTML shell, Tailwind config (colors, shadows, keyframes), global CSS (fonts, shimmer, focus ring, expand-grid animation), script tags |
| `app.jsx`       | Root `App` component — state, filter pipeline, sort, header (mobile + desktop layouts), bucket chip row, grid render logic (incl. compact full-row expand chunking), `TabButton`, `EmptyState`, `FilterFieldRow`, `useColumns` hook |
| `card.jsx`      | `LotCard`, `LotExpandPanel`, `SkeletonCard`, `LotImage` (with shimmer + broken fallback), `StarButton`, `DayBadge`, `BatBucketPill`, `ConditionPill` |
| `icons.jsx`     | Hand-rolled lucide-style icon components. **Replace with `lucide-react`** in production. |
| `mock-data.jsx` | 18 sample lots covering: both days, all 5 conditions, watched / not-watched, bat / non-bat, multiple buckets, empty buckets, broken images, empty descriptions, long titles. **Discard in production** — wire to real data. |

To run the prototype locally for reference: open `index.html` directly in a browser (no build step needed — Tailwind CDN + Babel standalone do the work).
