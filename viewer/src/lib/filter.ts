import type { Lot, Tab, DayFilter } from './types';

export function filterLots(
  lots: Lot[],
  {
    tab,
    query,
    dayFilter,
    category,
    batBucket,
    watched,
  }: {
    tab: Tab;
    query: string;
    dayFilter: DayFilter;
    category: string;
    batBucket: string;
    watched: Set<string>;
  }
): Lot[] {
  let rows = lots.slice();
  const q = query.trim().toLowerCase();

  if (tab === 'watched') {
    rows = rows.filter((l) => watched.has(l.lot_number));
  } else {
    if (tab === 'bat') {
      rows = rows.filter((l) => l.is_bat);
      if (batBucket !== 'All') {
        rows = rows.filter((l) => l.bat_buckets.includes(batBucket));
      }
    } else if (tab === 'nice') {
      rows = rows.filter((l) => l.is_nice_pick);
    }
    if (dayFilter !== 'Both') rows = rows.filter((l) => l.day === dayFilter);
    if (category !== 'All') rows = rows.filter((l) => l.category === category);
  }

  if (q) {
    rows = rows.filter(
      (l) =>
        l.title.toLowerCase().includes(q) ||
        l.description.toLowerCase().includes(q) ||
        l.lot_number.toLowerCase().includes(q) ||
        l.category.toLowerCase().includes(q) ||
        l.subcategory.toLowerCase().includes(q)
    );
  }

  return rows;
}
