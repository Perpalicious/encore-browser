import { describe, it, expect } from 'vitest';
import type { Lot } from './types';
import { buildLotViews, closeMs, closeLabel, closeLabelLong } from './lotView';
import { sortLots } from './sort';
import { filterLots } from './filter';

/**
 * Closing times — the auction-day feature.
 *
 * `close_at` has always been scraped and was silently dropped by the build, so
 * every bundle in existence today has none. That makes "absent" the normal
 * case, not the edge case, and it is asserted as hard as the present one.
 */

function lot(partial: Partial<Lot> & { lot_number: string }): Lot {
  return {
    day: 'Sunday',
    title: `Lot ${partial.lot_number}`,
    description: '',
    condition: 'Good',
    thumb_url: '',
    image_url: '',
    lot_url: 'https://encoreauctions.hibid.com/lot/1/x',
    category: 'Tools',
    subcategory: 'Hand Tools',
    category_path: ['Tools', 'Hand Tools'],
    is_bat: false,
    bat_buckets: [],
    confidence: 'low',
    est_retail_price: null,
    est_resale_low: null,
    est_resale_high: null,
    resale_confidence: null,
    resale_outlook: null,
    resale_reasoning: null,
    ...partial,
  };
}

/** A fixed local wall-clock time, so the label assertions are timezone-proof. */
function atLocal(h: number, m: number): { iso: string; ms: number } {
  const d = new Date(2026, 7, 9, h, m, 0, 0); // 9 Aug 2026, local
  return { iso: d.toISOString(), ms: d.getTime() };
}

describe('closeMs', () => {
  it('parses an ISO string with an offset', () => {
    expect(closeMs(lot({ lot_number: 'S-1', close_at: '2026-08-09T13:04:00-04:00' }))).toBe(
      Date.parse('2026-08-09T13:04:00-04:00')
    );
  });

  it('is null when the bundle predates the field', () => {
    expect(closeMs(lot({ lot_number: 'S-1' }))).toBeNull();
    expect(closeMs(lot({ lot_number: 'S-1', close_at: null }))).toBeNull();
    expect(closeMs(lot({ lot_number: 'S-1', close_at: '' }))).toBeNull();
  });

  it('is null rather than NaN on garbage', () => {
    expect(closeMs(lot({ lot_number: 'S-1', close_at: 'closing soon' }))).toBeNull();
  });

  it('is carried onto the view record', () => {
    const [v] = buildLotViews([lot({ lot_number: 'S-1', close_at: '2026-08-09T13:04:00-04:00' })]);
    expect(v.closeMs).toBe(Date.parse('2026-08-09T13:04:00-04:00'));
  });
});

describe('labels', () => {
  it('renders the compact card form', () => {
    expect(closeLabel(atLocal(13, 4).ms)).toBe('1:04p');
    expect(closeLabel(atLocal(9, 30).ms)).toBe('9:30a');
  });

  it('renders noon and midnight as 12, not 0', () => {
    expect(closeLabel(atLocal(12, 0).ms)).toBe('12:00p');
    expect(closeLabel(atLocal(0, 5).ms)).toBe('12:05a');
  });

  it('pads the minutes', () => {
    expect(closeLabel(atLocal(13, 4).ms)).toContain(':04');
  });

  it('gives the detail overlay a longer form with the day', () => {
    const long = closeLabelLong(atLocal(13, 4).ms);
    expect(long).toContain('Aug');
    expect(long).toMatch(/1:04/);
  });
});

describe("sortLots('close-asc')", () => {
  const early = lot({ lot_number: 'S-3', close_at: '2026-08-09T13:00:00-04:00' });
  const late = lot({ lot_number: 'S-1', close_at: '2026-08-09T15:00:00-04:00' });
  const untimed = lot({ lot_number: 'S-2' });

  it('orders by closing time, not lot number', () => {
    expect(sortLots([late, early], 'close-asc').map((l) => l.lot_number)).toEqual(['S-3', 'S-1']);
  });

  it('puts untimed lots last, so the actionable ones lead', () => {
    expect(sortLots([untimed, late, early], 'close-asc').map((l) => l.lot_number)).toEqual([
      'S-3',
      'S-1',
      'S-2',
    ]);
  });

  it('falls back to lot number when nothing has a time', () => {
    const a = lot({ lot_number: 'S-2' });
    const b = lot({ lot_number: 'S-1' });
    expect(sortLots([a, b], 'close-asc').map((l) => l.lot_number)).toEqual(['S-1', 'S-2']);
  });

  it('does not mutate the input array', () => {
    const rows = [late, early];
    sortLots(rows, 'close-asc');
    expect(rows.map((l) => l.lot_number)).toEqual(['S-1', 'S-3']);
  });
});

describe('filterLots hideEnded', () => {
  const now = Date.parse('2026-08-09T14:00:00-04:00');
  const closed = lot({ lot_number: 'S-1', close_at: '2026-08-09T13:00:00-04:00' });
  const open = lot({ lot_number: 'S-2', close_at: '2026-08-09T15:00:00-04:00' });
  const untimed = lot({ lot_number: 'S-3' });
  const base = {
    tab: 'all' as const,
    dayFilter: 'Both' as const,
    categoryPath: [],
    batBucket: null,
    watched: new Set<string>(),
  };

  it('drops lots whose time has passed', () => {
    const rows = filterLots([closed, open, untimed], { ...base, hideEnded: true, now });
    expect(rows.map((l) => l.lot_number)).toEqual(['S-2', 'S-3']);
  });

  it('keeps untimed lots — absent is not the same as ended', () => {
    const rows = filterLots([untimed], { ...base, hideEnded: true, now });
    expect(rows).toHaveLength(1);
  });

  it('does nothing when the toggle is off', () => {
    expect(filterLots([closed, open], { ...base, now })).toHaveLength(2);
  });

  it('does nothing without a clock, rather than treating everything as ended', () => {
    expect(filterLots([closed, open], { ...base, hideEnded: true })).toHaveLength(2);
  });
});
