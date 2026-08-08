export type Condition = 'New' | 'Like New' | 'Good' | 'Fair' | 'Heavily Used';
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
 *  - 'retail-desc': by estimated retail price
 */
export type SortKey = 'lot' | 'resale-desc' | 'resale-asc' | 'retail-desc' | 'close-asc';

/** Condition values in canonical (best → worst) order for filter chips. */
export const CONDITION_ORDER: Condition[] = [
  'New',
  'Like New',
  'Good',
  'Fair',
  'Heavily Used',
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
  // Estimated retail price from HiBid (null when unknown).
  est_retail_price: number | null;
  // Resale valuation — all null for lots the valuation pass did not cover.
  est_resale_low: number | null;
  est_resale_high: number | null;
  resale_confidence: Confidence | null;
  resale_outlook: ResaleOutlook | null;
  resale_reasoning: string | null;
  // Personal match — optional: absent (or null) on lots from bundles built
  // before the personal-match pass, and on lots the pass didn't flag.
  personal_match?: boolean | null;
  personal_tags?: string[] | null;
  match_strength?: string | null;
  match_types?: string[] | null;
  personal_reasoning?: string | null;
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
}
