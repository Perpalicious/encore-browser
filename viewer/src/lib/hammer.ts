import type { Bundle, HammerWeek, Lot } from './types';
import { formatMoney } from './resale';

/**
 * Hammer history — what this same product actually sold for in earlier Encore
 * auctions (build/hammer.py, from tools/hammer.py's post-close pull).
 *
 * This is a display aid at bid time, and a STRONGER figure than the resale
 * estimate beside it: real transactions in this venue, not a model's guess at
 * what a thing is worth elsewhere. It is deliberately typeset smaller and in
 * mono so it reads as history rather than as a second valuation competing with
 * the first (docs/design/README.md § "The signal system").
 *
 * Coverage is partial by construction — about one lot in three is a repeat
 * product — so every consumer must tolerate `null`: no `--hammer` at build
 * time, no `hammer_key` on the lot, and no entry in the map all land here.
 */

/** The product-key → history map, as it ships in the bundle. */
export type HammerIndex = Record<string, { weeks: HammerWeek[] }>;

/**
 * This lot's history, newest week first, or null when it has none.
 *
 * Split from `hammerFor` so the grid can resolve thousands of lots against one
 * already-unwrapped map without touching the bundle each time.
 */
export function hammerWeeks(lot: Lot, index: HammerIndex | undefined): HammerWeek[] | null {
  if (!index || !lot.hammer_key) return null;
  const entry = index[lot.hammer_key];
  if (!entry || !entry.weeks || entry.weeks.length === 0) return null;
  return entry.weeks;
}

/** The same lookup against a whole bundle, for a single lot. */
export function hammerFor(lot: Lot, bundle: Bundle | null | undefined): HammerWeek[] | null {
  return hammerWeeks(lot, bundle?.hammer);
}

/**
 * How much of the line fits. The card is 150–260px wide depending on density,
 * so the line sheds detail rather than overflowing: the range goes first
 * (median already says roughly what it said), then the unsold count.
 */
export type HammerDetail = 'full' | 'no-range' | 'minimal';

/** The detail level a column of `colW` pixels can carry. */
export function hammerDetailFor(colW: number): HammerDetail {
  if (colW >= 230) return 'full';
  if (colW >= 170) return 'no-range';
  return 'minimal';
}

/** "$9–$22", or a single bound when only one is known. */
export function hammerRange(week: HammerWeek): string | null {
  const { low, high } = week;
  if (low !== null && high !== null) {
    return low === high ? formatMoney(low) : `${formatMoney(low)}–${formatMoney(high)}`;
  }
  if (low !== null) return formatMoney(low);
  if (high !== null) return formatMoney(high);
  return null;
}

/**
 * The compact card line for one week:
 *
 *     Sold 6× · med $14 · $9–$22 · 3 unsold
 *
 * A product that was listed and sold nothing reads "Listed 12× · none sold" —
 * that is information, and it must never render as "$0" (a zero-bid lot has no
 * price, not a price of zero).
 */
export function hammerLine(week: HammerWeek, detail: HammerDetail = 'full'): string {
  if (week.sold === 0) {
    const listed = week.unsold;
    return listed > 0 ? `Listed ${listed}× · none sold` : 'None sold';
  }

  const parts = [`Sold ${week.sold}×`];
  if (week.median !== null) parts.push(`med ${formatMoney(week.median)}`);

  const range = hammerRange(week);
  if (detail === 'full' && range && week.sold > 1) parts.push(range);
  if (detail !== 'minimal' && week.unsold > 0) parts.push(`${week.unsold} unsold`);

  return parts.join(' · ');
}

/** "13 Sep" — the detail table's week label. Falls back to the raw date. */
export function hammerDateLabel(closeDate: string): string {
  const ms = Date.parse(`${closeDate}T12:00:00`);
  if (!Number.isFinite(ms)) return closeDate;
  return new Date(ms).toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
}
