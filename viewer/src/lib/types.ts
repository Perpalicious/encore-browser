export type Condition = 'New' | 'Like New' | 'Good' | 'Fair' | 'Heavily Used';
export type Confidence = 'low' | 'medium' | 'high';
export type ResaleOutlook = 'good' | 'fair' | 'poor';
export type DayFilter = 'Sunday' | 'Monday' | 'Both';
export type Density = 'standard' | 'compact';
export type Tab = 'all' | 'bat' | 'watched';

/**
 * Resale confidence filter: 'all' = no filter, 'high' = high only,
 * 'medium-plus' = medium or high. Lots with no resale data are excluded
 * whenever the filter is not 'all'.
 */
export type ConfidenceFilter = 'all' | 'high' | 'medium-plus';

export interface Lot {
  day: string;
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
