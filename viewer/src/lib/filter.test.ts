import { describe, it, expect } from 'vitest';
import { filterLots } from './filter';
import type { Lot, Condition } from './types';

function lot(lot_number: string, opts: Partial<Lot> = {}): Lot {
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

const LOTS: Lot[] = [
  lot('1', { condition: 'New', is_bat: true, bat_buckets: ['Lego'] }),
  lot('2', { condition: 'Good', is_bat: true, bat_buckets: ['Lego'] }),
  lot('3', { condition: 'Like New' }),
  lot('4', { condition: null }), // no condition
  lot('5', { condition: 'New', is_bat: true, bat_buckets: ['Power tools'] }),
];

const base = {
  tab: 'all' as const,
  dayFilter: 'Both' as const,
  categoryPath: [] as string[],
  batBucket: null as string | null,
  watched: new Set<string>(),
};

describe('filterLots condition filter', () => {
  it('no conditions selected = no condition narrowing', () => {
    const out = filterLots(LOTS, { ...base, conditions: new Set() });
    expect(out).toHaveLength(5);
  });

  it('narrows to lots whose condition is selected', () => {
    const conditions = new Set<Condition>(['New']);
    const out = filterLots(LOTS, { ...base, conditions });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['1', '5']);
  });

  it('multi-select is a union across selected conditions', () => {
    const conditions = new Set<Condition>(['New', 'Good']);
    const out = filterLots(LOTS, { ...base, conditions });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['1', '2', '5']);
  });

  it('excludes lots with no condition while a filter is active', () => {
    const conditions = new Set<Condition>(['Like New']);
    const out = filterLots(LOTS, { ...base, conditions });
    expect(out.map((l) => l.lot_number)).toEqual(['3']);
    expect(out.find((l) => l.lot_number === '4')).toBeUndefined();
  });

  it('composes with the bat bucket filter (narrows within the bucket)', () => {
    const out = filterLots(LOTS, {
      ...base,
      tab: 'bat',
      batBucket: 'Lego',
      conditions: new Set<Condition>(['New']),
    });
    // Bucket Lego = lots 1,2; condition New within that = lot 1 only.
    expect(out.map((l) => l.lot_number)).toEqual(['1']);
  });
});
