export type Condition = 'New' | 'Like New' | 'Good' | 'Fair' | 'Heavily Used';
export type Confidence = 'low' | 'medium' | 'high';
export type DayFilter = 'Sunday' | 'Monday' | 'Both';
export type Density = 'standard' | 'compact';
export type Tab = 'all' | 'bat' | 'nice' | 'watched';

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
  is_bat: boolean;
  bat_buckets: string[];
  is_nice_pick: boolean;
  nice_pick_reason: string;
  confidence: Confidence;
}
