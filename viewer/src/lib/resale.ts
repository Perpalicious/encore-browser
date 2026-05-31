import type { Lot, ConfidenceFilter } from './types';

/**
 * Resale-valuation helpers. The valuation pass covers only a subset of lots,
 * so every consumer must tolerate missing data: `hasResale` is the gate, and
 * the rest return null / false when a lot was not valued.
 */

/** True when the lot has a usable resale range (at least one of low/high). */
export function hasResale(lot: Lot): boolean {
  return lot.est_resale_low !== null || lot.est_resale_high !== null;
}

/**
 * The representative resale figure: the mean of low and high. If only one
 * bound is present, that bound is used. Null when the lot has no resale data.
 */
export function resaleMean(lot: Lot): number | null {
  const { est_resale_low: lo, est_resale_high: hi } = lot;
  if (lo !== null && hi !== null) return (lo + hi) / 2;
  if (lo !== null) return lo;
  if (hi !== null) return hi;
  return null;
}

/** Format a dollar amount compactly, e.g. 54.5 -> "$55", 1200 -> "$1,200". */
export function formatMoney(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '—';
  return '$' + Math.round(value).toLocaleString('en-US');
}

/** Format the resale range "$40–$70" (or a single bound if only one exists). */
export function resaleRange(lot: Lot): string {
  const { est_resale_low: lo, est_resale_high: hi } = lot;
  if (lo !== null && hi !== null) return `${formatMoney(lo)}–${formatMoney(hi)}`;
  if (lo !== null) return `≥ ${formatMoney(lo)}`;
  if (hi !== null) return `≤ ${formatMoney(hi)}`;
  return '—';
}

/**
 * A "potential resale" is the demand-aware pick: there's resale data, the
 * market outlook is good or fair (not poor), AND confidence is medium or high
 * (not low). This omits high-confidence-but-poor-market items like used shoes.
 */
export function isPotentialResale(lot: Lot): boolean {
  if (!hasResale(lot)) return false;
  const outlookOk = lot.resale_outlook === 'good' || lot.resale_outlook === 'fair';
  const confOk = lot.resale_confidence === 'medium' || lot.resale_confidence === 'high';
  return outlookOk && confOk;
}

/**
 * Whether a lot passes the resale-confidence filter. With 'all' everything
 * passes; otherwise only lots whose resale_confidence meets the bar pass —
 * which means un-valued lots (null confidence) are excluded.
 */
export function confidencePasses(lot: Lot, filter: ConfidenceFilter): boolean {
  if (filter === 'all') return true;
  if (filter === 'high') return lot.resale_confidence === 'high';
  // 'medium-plus'
  return lot.resale_confidence === 'high' || lot.resale_confidence === 'medium';
}
