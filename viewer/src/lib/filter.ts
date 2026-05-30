import type { Lot, Tab, DayFilter } from './types';
import { pathHasPrefix } from './categoryTree';

/**
 * Apply the structural filters: tab, day, hierarchical category, bat bucket.
 * Search is handled separately (see lib/search.ts) so it can run as a fuzzy
 * pass narrowed to whatever this function returns.
 */
export function filterLots(
  lots: Lot[],
  {
    tab,
    dayFilter,
    categoryPath,
    batBucket,
    watched,
  }: {
    tab: Tab;
    dayFilter: DayFilter;
    categoryPath: string[];
    batBucket: string;
    watched: Set<string>;
  }
): Lot[] {
  let rows = lots.slice();

  if (tab === 'watched') {
    rows = rows.filter((l) => watched.has(l.lot_number));
  } else {
    if (tab === 'bat') {
      rows = rows.filter((l) => l.is_bat);
      if (batBucket !== 'All') {
        rows = rows.filter((l) => l.bat_buckets.includes(batBucket));
      }
    }
    if (dayFilter !== 'Both') rows = rows.filter((l) => l.day === dayFilter);
    if (categoryPath.length > 0) {
      rows = rows.filter((l) => pathHasPrefix(l.category_path, categoryPath));
    }
  }

  return rows;
}
