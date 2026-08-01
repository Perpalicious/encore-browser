import type {
  Lot,
  Tab,
  DayFilter,
  ConfidenceFilter,
  OutlookFilter,
  Condition,
} from './types';
import { pathHasPrefix } from './categoryTree';
import { confidencePasses, isPotentialResale } from './resale';
import { isPersonalPick } from './personal';
import { dayLetter } from './lotView';

/**
 * Match a lot against the day filter.
 *
 * NOT `lot.day === dayFilter`: on two-auction weeks the scrape leaves `day` as
 * an empty string on every Monday lot, so a direct comparison matched nothing
 * and the Monday filter silently returned zero results. `dayLetter` derives the
 * day from the 'S-'/'M-' lot-number prefix, which the combine step applies to
 * every row.
 */
function dayMatches(lot: Lot, dayFilter: DayFilter): boolean {
  if (dayFilter === 'Both') return true;
  return dayLetter(lot) === (dayFilter === 'Monday' ? 'M' : 'S');
}

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
    outlookFilter = 'all',
    potentialOnly = false,
    personalOnly = false,
    conditions,
  }: {
    tab: Tab;
    dayFilter: DayFilter;
    categoryPath: string[];
    batBucket: string | null;
    watched: Set<string>;
    confidenceFilter?: ConfidenceFilter;
    outlookFilter?: OutlookFilter;
    potentialOnly?: boolean;
    personalOnly?: boolean;
    conditions?: Set<Condition>;
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
    if (dayFilter !== 'Both') rows = rows.filter((l) => dayMatches(l, dayFilter));
  } else {
    if (dayFilter !== 'Both') rows = rows.filter((l) => dayMatches(l, dayFilter));
    if (categoryPath.length > 0) {
      rows = rows.filter((l) => pathHasPrefix(l.category_path, categoryPath));
    }
  }

  // Resale + personal-pick filters apply on every tab, narrowing the current
  // view further. Lots without personal-match data are excluded while the
  // personal filter is on (personal_match must be exactly true).
  if (personalOnly) rows = rows.filter(isPersonalPick);
  if (potentialOnly) rows = rows.filter(isPotentialResale);
  if (confidenceFilter !== 'all') {
    rows = rows.filter((l) => confidencePasses(l, confidenceFilter));
  }
  // Outlook is the exact market read, where `potentialOnly` is the combined
  // demand-aware shortcut (outlook AND confidence). They compose.
  if (outlookFilter !== 'all') {
    rows = rows.filter((l) => l.resale_outlook === outlookFilter);
  }

  // Condition chips: when any are selected, keep only lots whose condition is
  // among them. Lots with no condition are excluded while the filter is active.
  if (conditions && conditions.size > 0) {
    rows = rows.filter((l) => l.condition !== null && conditions.has(l.condition));
  }

  return rows;
}
