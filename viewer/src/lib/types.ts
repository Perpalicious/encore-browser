export type Condition = 'New' | 'Like New' | 'Good' | 'Fair' | 'Heavily Used';
export type Confidence = 'low' | 'medium' | 'high';
export type DayFilter = 'Sunday' | 'Monday' | 'Both';
export type Density = 'standard' | 'compact';
export type Tab = 'all' | 'bat' | 'watched';

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
