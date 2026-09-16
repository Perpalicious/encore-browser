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

/** One condition's history for a title: the grade as HiBid spells it, and its weeks. */
export interface HammerGrade {
  condition: string;
  weeks: HammerWeek[];
}

/**
 * Everything the bundle knows about this lot's title.
 *
 * `own` is the lot's exact (title + condition) history, and is what the card
 * line shows when present. `others` are the same title's OTHER conditions,
 * nearest grade first as the build ordered them (build/hammer.py
 * CONDITION_LADDER); the card falls back to the first of them, always under
 * that grade's label, when `own` is null. The two are never blended: a `Good`
 * unit that never sold is not priced by the `Excellent` one next to it.
 */
export interface HammerHistory {
  own: HammerWeek[] | null;
  others: HammerGrade[];
}

function weeksAt(index: HammerIndex, key: string): HammerWeek[] | null {
  const entry = index[key];
  if (!entry || !entry.weeks || entry.weeks.length === 0) return null;
  return entry.weeks;
}

/** The condition half of a `"TITLE|CONDITION"` key. */
export function keyCondition(key: string): string {
  const bar = key.lastIndexOf('|');
  return bar < 0 ? '' : key.slice(bar + 1);
}

/**
 * This lot's history, or null when there is nothing at all to show.
 *
 * Split from `hammerFor` so the grid can resolve thousands of lots against one
 * already-unwrapped map without touching the bundle each time.
 */
export function hammerHistory(lot: Lot, index: HammerIndex | undefined): HammerHistory | null {
  if (!index) return null;
  const own = lot.hammer_key ? weeksAt(index, lot.hammer_key) : null;
  const others: HammerGrade[] = [];
  for (const key of lot.hammer_alt_keys ?? []) {
    const weeks = weeksAt(index, key);
    if (weeks) others.push({ condition: keyCondition(key), weeks });
  }
  if (!own && others.length === 0) return null;
  return { own, others };
}

/** This lot's own history only, newest week first, or null when it has none. */
export function hammerWeeks(lot: Lot, index: HammerIndex | undefined): HammerWeek[] | null {
  return hammerHistory(lot, index)?.own ?? null;
}

/** The same lookup against a whole bundle, for a single lot. */
export function hammerFor(lot: Lot, bundle: Bundle | null | undefined): HammerHistory | null {
  return hammerHistory(lot, bundle?.hammer);
}

/**
 * Short grade labels for the borrowed-history line, where the full HiBid
 * spelling ("BRAND NEW - OPEN BOX") would eat the whole card. Anything HiBid
 * adds later falls back to title case of its own name.
 */
const GRADE_SHORT: Record<string, string> = {
  'BRAND NEW - SEALED': 'Sealed',
  'BRAND NEW - OPEN BOX': 'Open box',
  'NEW (ADJUSTED QUANTITY)': 'New (adj.)',
  'NEW WITH DEFECTS': 'New w/ defects',
  'BEST BEFORE (GROCERY)': 'Best before',
  EXCELLENT: 'Excellent',
  GOOD: 'Good',
  FAIR: 'Fair',
  'HEAVILY USED': 'Heavily used',
  'FOR PARTS ONLY': 'Parts only',
};

/** "Open box", "Excellent", … for a key's condition half. */
export function gradeLabel(condition: string): string {
  const upper = condition.toUpperCase();
  if (GRADE_SHORT[upper]) return GRADE_SHORT[upper];
  if (!upper) return 'No grade';
  return upper.charAt(0) + upper.slice(1).toLowerCase();
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

/**
 * The card line for a whole history: the lot's own latest week when it has one,
 * else the nearest other grade's latest week PREFIXED with that grade —
 *
 *     Excellent: Sold 6× · med $14
 *
 * The prefix is not decoration. Without it a `For Parts Only` lot would show
 * the `Excellent` median as if it were its own. A borrowed line also drops one
 * level of detail to pay for the label.
 */
export function hammerCardLine(history: HammerHistory, detail: HammerDetail = 'full'): string {
  if (history.own) return hammerLine(history.own[0], detail);
  const grade = history.others[0];
  const less: HammerDetail = detail === 'full' ? 'no-range' : 'minimal';
  return `${gradeLabel(grade.condition)}: ${hammerLine(grade.weeks[0], less)}`;
}

/** "13 Sep" — the detail table's week label. Falls back to the raw date. */
export function hammerDateLabel(closeDate: string): string {
  const ms = Date.parse(`${closeDate}T12:00:00`);
  if (!Number.isFinite(ms)) return closeDate;
  return new Date(ms).toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
}
