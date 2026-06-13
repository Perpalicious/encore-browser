import { describe, it, expect } from 'vitest';
import { sortLots } from './sort';
import type { Lot } from './types';

function lot(
  lot_number: string,
  opts: Partial<Lot> = {}
): Lot {
  return {
    day: 'Sunday',
    lot_number,
    title: `Lot ${lot_number}`,
    description: '',
    condition: null,
    thumb_url: '',
    image_url: '',
    lot_url: '',
    category: '',
    subcategory: '',
    category_path: [],
    is_bat: false,
    bat_buckets: [],
    confidence: 'low',
    est_retail_price: null,
    est_resale_low: null,
    est_resale_high: null,
    resale_confidence: null,
    resale_outlook: null,
    resale_reasoning: null,
    ...opts,
  };
}

// Resale means: a=50, b=200, c=125, d=null (no resale data)
const a = lot('a', { est_resale_low: 40, est_resale_high: 60 }); // mean 50
const b = lot('b', { est_resale_low: 150, est_resale_high: 250 }); // mean 200
const c = lot('c', { est_resale_high: 125 }); // single bound -> 125
const d = lot('d'); // no resale data

describe('sortLots', () => {
  it('default "lot" order keeps Bat-first / Sunday-first / lot-number', () => {
    const lots = [
      lot('200', { is_bat: false, day: 'Monday' }),
      lot('100', { is_bat: true, day: 'Monday' }),
      lot('050', { is_bat: false, day: 'Sunday' }),
    ];
    const out = sortLots(lots, 'lot').map((l) => l.lot_number);
    // bat lot first, then non-bat sorted Sunday-before-Monday, then lot number
    expect(out).toEqual(['100', '050', '200']);
  });

  it('resale high → low sorts by resale mean descending', () => {
    const out = sortLots([a, c, b], 'resale-desc').map((l) => l.lot_number);
    expect(out).toEqual(['b', 'c', 'a']); // 200, 125, 50
  });

  it('resale low → high sorts by resale mean ascending', () => {
    const out = sortLots([b, a, c], 'resale-asc').map((l) => l.lot_number);
    expect(out).toEqual(['a', 'c', 'b']); // 50, 125, 200
  });

  it('lots without resale data sort to the END of value sorts', () => {
    const desc = sortLots([d, a, b], 'resale-desc').map((l) => l.lot_number);
    expect(desc).toEqual(['b', 'a', 'd']); // d (null) last even descending
    const asc = sortLots([d, a, b], 'resale-asc').map((l) => l.lot_number);
    expect(asc).toEqual(['a', 'b', 'd']); // d (null) still last
  });

  it('retail high → low sorts by est_retail_price descending, nulls last', () => {
    const lots = [
      lot('x', { est_retail_price: 30 }),
      lot('y', { est_retail_price: 300 }),
      lot('z'), // null retail
      lot('w', { est_retail_price: 150 }),
    ];
    const out = sortLots(lots, 'retail-desc').map((l) => l.lot_number);
    expect(out).toEqual(['y', 'w', 'x', 'z']);
  });

  it('ties break by lot number; all-null falls back to lot number', () => {
    const out = sortLots(
      [lot('c'), lot('a'), lot('b')],
      'resale-desc'
    ).map((l) => l.lot_number);
    expect(out).toEqual(['a', 'b', 'c']);
  });

  it('does not mutate the input array', () => {
    const input = [b, a];
    sortLots(input, 'resale-asc');
    expect(input.map((l) => l.lot_number)).toEqual(['b', 'a']);
  });
});
