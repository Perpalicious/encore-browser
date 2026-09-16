/**
 * HiBid's own condition vocabulary, passed through 1:1 by the scraper. The old
 * five-label scheme ('New' | 'Like New' | ...) came from a pre-data design spec;
 * 'Like New' in particular never appeared in a single listing, and covered 53%
 * of lots by merging 'Excellent' with 'Brand New - Open Box'.
 *
 * `string` rather than a closed union on purpose: build/__main__.py warns about
 * a condition HiBid adds later but still ships it, and the viewer must render
 * it (neutral colour, no chip) rather than break.
 */
export type Condition = string;
export type Confidence = 'low' | 'medium' | 'high';
export type ResaleOutlook = 'good' | 'fair' | 'poor';
export type DayFilter = 'Sunday' | 'Monday' | 'Both';
export type Density = 'standard' | 'compact';
export type Tab = 'all' | 'bat' | 'watched';

/** Desktop layout: the card grid, or one row per lot. */
export type ViewMode = 'grid' | 'list';
/** Mobile layout: 78px rows, or the card grid at the chosen column count. */
export type MobileView = 'rows' | 'cards';
/** Mobile card columns. 3 is the default — ~9 lots/screen at 113px targets. */
export type MobileCols = 2 | 3 | 4;

/**
 * Item-list sort order. 'lot' is the default (Bat-first / Sunday-first /
 * lot-number). The value-based orders sort lots with no data to the end.
 *  - 'resale-desc' / 'resale-asc': by resale mean (low/high midpoint)
 *
 * There was a 'retail-desc' here until 2026-09-10. HiBid stopped publishing an
 * estimated retail price and it was dropped from the pipeline entirely — see
 * scraper/condition.py. lib/persist.ts drops the stale key from a saved
 * preference, so anyone whose browser still remembers it lands back on 'lot'.
 */
export type SortKey = 'lot' | 'resale-desc' | 'resale-asc' | 'close-asc';

/**
 * Condition values in canonical (best → worst) order for filter chips. Mirrors
 * CONDITION_LABELS in scraper/condition.py — keep the two in step.
 */
export const CONDITION_ORDER: Condition[] = [
  'Brand New - Sealed',
  'Brand New - Open Box',
  'New (Adjusted Quantity)',
  'Best Before (Grocery)',
  'Excellent',
  'Good',
  'New With Defects',
  'Fair',
  'Heavily Used',
  'For Parts Only',
  'Do Not Bid',
];

/**
 * Resale confidence filter: 'all' = no filter, 'high' = high only,
 * 'medium-plus' = medium or high. Lots with no resale data are excluded
 * whenever the filter is not 'all'.
 */
export type ConfidenceFilter = 'all' | 'high' | 'medium-plus';

/**
 * Resale-outlook filter: 'all' = no filter, otherwise the exact outlook.
 *
 * The design handoff assumes four outlook steps (Poor/Fair/Good/Strong); our
 * resale pass only ever emits three, so this deliberately has no fourth value.
 * Lots with no outlook are excluded whenever the filter is not 'all'.
 */
export type OutlookFilter = 'all' | ResaleOutlook;

/** Outlook values worst → best, for the filter's segmented control. */
export const OUTLOOK_ORDER: ResaleOutlook[] = ['poor', 'fair', 'good'];

export interface Lot {
  day: string;
  /**
   * ISO-8601 with a real UTC offset, e.g. '2026-08-09T13:04:00-04:00'.
   * Optional: bundles built before the field was carried through the pipeline
   * have none, which is why every closing-time affordance is feature-detected.
   */
  close_at?: string | null;
  /** Free-form level under the Bat's List bucket, e.g. 'scrub brushes'. */
  bat_subtype?: string | null;
  lot_number: string;
  title: string;
  description: string;
  condition: Condition | null;
  thumb_url: string;
  image_url: string;
  lot_url: string;
  category: string;
  subcategory: string;
  category_path: string[];
  is_bat: boolean;
  bat_buckets: string[];
  confidence: Confidence;
  // Resale valuation — all null for lots the valuation pass did not cover.
  est_resale_low: number | null;
  est_resale_high: number | null;
  resale_confidence: Confidence | null;
  resale_outlook: ResaleOutlook | null;
  resale_reasoning: string | null;
  /**
   * Key into `Bundle.hammer` — what this same product (title + condition) sold
   * for in earlier auctions. Null on the ~two thirds of lots whose product has
   * no recorded history, and absent entirely on a bundle built without
   * `--hammer`. The history is NOT copied onto the lot: 58 lots routinely share
   * one product, so they share one entry in the map.
   */
  hammer_key?: string | null;
  /**
   * Keys into `Bundle.hammer` for the SAME title in OTHER conditions that have
   * history, nearest grade first. A `Good` lot whose title only ever ran as
   * `Excellent` has no `hammer_key` but one entry here. Shown under that grade's
   * own label, never as this lot's history. Null/absent when there are none.
   */
  hammer_alt_keys?: string[] | null;
  // Personal match — optional: absent (or null) on lots from bundles built
  // before the personal-match pass, and on lots the pass didn't flag.
  personal_match?: boolean | null;
  personal_tags?: string[] | null;
  match_strength?: string | null;
  match_types?: string[] | null;
  personal_reasoning?: string | null;
  // Scrape identity — optional: the ISO timestamp of the scrape run that first
  // saw the lot, and the 1-based index of that run in `Bundle.scrapes`. Both
  // absent on bundles built from raw files that predate the field.
  first_seen?: string | null;
  scrape?: number | null;
}

/** One scrape run of the week, as numbered by build/scrapes.py. */
export interface ScrapeInfo {
  /** 1-based index; `Lot.scrape` points here. */
  scrape: number;
  /** ISO timestamp of the run's start — the stable identity a filter stores. */
  at: string;
  /** "Tue Sep 15" (with a time appended only when two runs share a day). */
  label: string;
  count: number;
}

/**
 * The viewer bundle, produced by `python -m build`. `bucket_groups` maps each
 * Bat's List bucket present in the data to its group (from buckets.yaml;
 * unknown buckets map to "Other"). `groups` lists the groups that contain
 * items, in buckets.yaml order ("Other" last).
 */
export interface Bundle {
  lots: Lot[];
  bucket_groups: Record<string, string>;
  groups: string[];
  /** Absent or empty on older bundles; the viewer shows the scrape filter only with 2+. */
  scrapes?: ScrapeInfo[];
  /**
   * Product key → what that product actually sold for, week by week, newest
   * first. Absent unless the bundle was built with `--hammer`; see
   * build/hammer.py.
   */
  hammer?: Record<string, { weeks: HammerWeek[] }>;
}

/**
 * One past auction's result for one product. `median`/`low`/`high` are over
 * SOLD lots only and are null when nothing sold — `unsold` is counted and
 * shown, never rendered as "$0".
 */
export interface HammerWeek {
  /** YYYY-MM-DD, the date that auction closed. */
  close_date: string;
  sold: number;
  unsold: number;
  median: number | null;
  low: number | null;
  high: number | null;
}
