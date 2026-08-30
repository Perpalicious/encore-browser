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
  lot('1', { condition: 'Brand New - Sealed', is_bat: true, bat_buckets: ['Lego'] }),
  lot('2', { condition: 'Good', is_bat: true, bat_buckets: ['Lego'] }),
  lot('3', { condition: 'Brand New - Open Box' }),
  lot('4', { condition: null }), // no condition
  lot('5', { condition: 'Brand New - Sealed', is_bat: true, bat_buckets: ['Power tools'] }),
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
    const conditions = new Set<Condition>(['Brand New - Sealed']);
    const out = filterLots(LOTS, { ...base, conditions });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['1', '5']);
  });

  it('multi-select is a union across selected conditions', () => {
    const conditions = new Set<Condition>(['Brand New - Sealed', 'Good']);
    const out = filterLots(LOTS, { ...base, conditions });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['1', '2', '5']);
  });

  it('excludes lots with no condition while a filter is active', () => {
    // Open-box is its own grade now, not merged with 'Excellent'.
    const conditions = new Set<Condition>(['Brand New - Open Box']);
    const out = filterLots(LOTS, { ...base, conditions });
    expect(out.map((l) => l.lot_number)).toEqual(['3']);
    expect(out.find((l) => l.lot_number === '4')).toBeUndefined();
  });

  it('composes with the bat bucket filter (narrows within the bucket)', () => {
    const out = filterLots(LOTS, {
      ...base,
      tab: 'bat',
      batBucket: 'Lego',
      conditions: new Set<Condition>(['Brand New - Sealed']),
    });
    // Bucket Lego = lots 1,2; Brand New - Sealed within that = lot 1 only.
    expect(out.map((l) => l.lot_number)).toEqual(['1']);
  });
});

describe('filterLots personal-picks filter', () => {
  const PERSONAL_LOTS: Lot[] = [
    lot('1', { personal_match: true, is_bat: true, bat_buckets: ['Lego'], condition: 'Brand New - Sealed' }),
    lot('2', { personal_match: false }),
    lot('3', { personal_match: null }),
    lot('4'), // fields absent entirely (older bundle)
    lot('5', { personal_match: true, day: 'Monday' }),
  ];

  it('off by default: all lots pass through', () => {
    const out = filterLots(PERSONAL_LOTS, { ...base });
    expect(out).toHaveLength(5);
  });

  it('on: keeps only personal_match === true (false/null/absent excluded)', () => {
    const out = filterLots(PERSONAL_LOTS, { ...base, personalOnly: true });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['1', '5']);
  });

  it('composes with the day filter', () => {
    const out = filterLots(PERSONAL_LOTS, {
      ...base,
      personalOnly: true,
      dayFilter: 'Monday',
    });
    expect(out.map((l) => l.lot_number)).toEqual(['5']);
  });

  it('composes with the bat bucket drill-down (narrows within the bucket)', () => {
    const out = filterLots(PERSONAL_LOTS, {
      ...base,
      tab: 'bat',
      batBucket: 'Lego',
      personalOnly: true,
    });
    expect(out.map((l) => l.lot_number)).toEqual(['1']);
  });

  it('composes with the condition filter', () => {
    const out = filterLots(PERSONAL_LOTS, {
      ...base,
      personalOnly: true,
      conditions: new Set<Condition>(['Brand New - Sealed']),
    });
    expect(out.map((l) => l.lot_number)).toEqual(['1']);
  });

  it('composes with the resale confidence filter (both must pass)', () => {
    const lots = [
      lot('1', { personal_match: true, resale_confidence: 'high', est_resale_low: 10, est_resale_high: 20 }),
      lot('2', { personal_match: true }), // personal but un-valued
      lot('3', { resale_confidence: 'high', est_resale_low: 10, est_resale_high: 20 }), // valued but not personal
    ];
    const out = filterLots(lots, {
      ...base,
      personalOnly: true,
      confidenceFilter: 'high',
    });
    expect(out.map((l) => l.lot_number)).toEqual(['1']);
  });

  it('older bundles (no personal fields anywhere) are unaffected when off, empty when on', () => {
    const older = [lot('1'), lot('2')];
    expect(filterLots(older, { ...base })).toHaveLength(2);
    expect(filterLots(older, { ...base, personalOnly: true })).toHaveLength(0);
  });
});
