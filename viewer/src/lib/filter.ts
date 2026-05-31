import type { Lot, Tab, DayFilter, ConfidenceFilter } from './types';
import { pathHasPrefix } from './categoryTree';
import { confidencePasses, isPotentialResale } from './resale';

/**
 * Apply the structural filters: tab, day, hierarchical category, bat bucket,
 * plus the resale filters (confidence + potential-resales). Search is handled
 * separately (see lib/search.ts) so it can run as a fuzzy pass narrowed to
 * whatever this function returns.
 *
 * The resale filters compose with — and narrow within — the current tab /
 * category / day view, on every tab.
 */
export function filterLots(
  lots: Lot[],
  {
    tab,
    dayFilter,
    categoryPath,
    batBucket,
    watched,
    confidenceFilter = 'all',
    potentialOnly = false,
  }: {
    tab: Tab;
    dayFilter: DayFilter;
    categoryPath: string[];
    batBucket: string | null;
    watched: Set<string>;
    confidenceFilter?: ConfidenceFilter;
    potentialOnly?: boolean;
  }
): Lot[] {
  let rows = lots.slice();

  if (tab === 'watched') {
    rows = rows.filter((l) => watched.has(l.lot_number));
  } else if (tab === 'bat') {
    // Bat's List is two-level: until a bucket is chosen, the group selector
    // drives the view and no items are shown (no thousands-of-items flood).
    if (batBucket === null) return [];
    rows = rows.filter((l) => l.is_bat && l.bat_buckets.includes(batBucket));
    if (dayFilter !== 'Both') rows = rows.filter((l) => l.day === dayFilter);
  } else {
    if (dayFilter !== 'Both') rows = rows.filter((l) => l.day === dayFilter);
    if (categoryPath.length > 0) {
      rows = rows.filter((l) => pathHasPrefix(l.category_path, categoryPath));
    }
  }

  // Resale filters apply on every tab, narrowing the current view further.
  if (potentialOnly) rows = rows.filter(isPotentialResale);
  if (confidenceFilter !== 'all') {
    rows = rows.filter((l) => confidencePasses(l, confidenceFilter));
  }

  return rows;
}
