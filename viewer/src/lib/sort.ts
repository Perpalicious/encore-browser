import type { Lot, SortKey } from './types';
import { resaleMean } from './resale';
import { closeMs } from './lotView';

/** Default order: Bat's List first, Sunday before Monday, then lot number. */
function defaultCompare(a: Lot, b: Lot): number {
  // 1. is_bat first
  if (a.is_bat !== b.is_bat) return a.is_bat ? -1 : 1;
  // 2. Sunday before Monday
  if (a.day !== b.day) return a.day === 'Sunday' ? -1 : 1;
  // 3. lot_number ascending
  return a.lot_number.localeCompare(b.lot_number);
}

/**
 * Closing time, ascending — the auction-day order. Lots with no time sort to
 * the end rather than the front, so a partially-timed bundle still leads with
 * the lots you can act on.
 */
function compareClose(a: Lot, b: Lot): number {
  const ca = closeMs(a);
  const cb = closeMs(b);
  if (ca === null && cb === null) return a.lot_number.localeCompare(b.lot_number);
  if (ca === null) return 1;
  if (cb === null) return -1;
  if (ca !== cb) return ca - cb;
  return a.lot_number.localeCompare(b.lot_number);
}

/** The value a value-based sort ranks on, or null when the lot has no data. */
function sortValue(lot: Lot, key: SortKey): number | null {
  const v = key === 'retail-desc' ? lot.est_retail_price : resaleMean(lot);
  if (v === null || Number.isNaN(v)) return null;
  return v;
}

/**
 * Sort lots by the chosen order. Value-based sorts ('resale-*', 'retail-desc')
 * push lots without that data to the end and tie-break by lot number, so they
 * never crash on nulls. The default 'lot' order keeps the curated Bat-first /
 * Sunday-first grouping.
 */
export function sortLots(lots: Lot[], sortKey: SortKey = 'lot'): Lot[] {
  if (sortKey === 'lot') return lots.slice().sort(defaultCompare);
  if (sortKey === 'close-asc') return lots.slice().sort(compareClose);

  const ascending = sortKey === 'resale-asc';
  return lots.slice().sort((a, b) => {
    const va = sortValue(a, sortKey);
    const vb = sortValue(b, sortKey);
    // Nulls always sort to the end, regardless of direction.
    if (va === null && vb === null) return a.lot_number.localeCompare(b.lot_number);
    if (va === null) return 1;
    if (vb === null) return -1;
    if (va !== vb) return ascending ? va - vb : vb - va;
    return a.lot_number.localeCompare(b.lot_number);
  });
}
