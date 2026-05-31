import { describe, it, expect } from 'vitest';
import type { Lot, Confidence, ResaleOutlook } from './types';
import {
  hasResale,
  resaleMean,
  formatMoney,
  resaleRange,
  isPotentialResale,
  confidencePasses,
} from './resale';
import { filterLots } from './filter';

function lot(partial: Partial<Lot> & { lot_number: string }): Lot {
  return {
    day: 'Sunday',
    title: `Lot ${partial.lot_number}`,
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
    ...partial,
  };
}

function valued(
  lot_number: string,
  low: number,
  high: number,
  resale_confidence: Confidence,
  resale_outlook: ResaleOutlook
): Lot {
  return lot({ lot_number, est_resale_low: low, est_resale_high: high, resale_confidence, resale_outlook });
}

describe('hasResale', () => {
  it('is false when both bounds are null', () => {
    expect(hasResale(lot({ lot_number: '1' }))).toBe(false);
  });
  it('is true when either bound is present', () => {
    expect(hasResale(lot({ lot_number: '1', est_resale_low: 10 }))).toBe(true);
    expect(hasResale(lot({ lot_number: '2', est_resale_high: 99 }))).toBe(true);
  });
});

describe('resaleMean', () => {
  it('averages low and high', () => {
    expect(resaleMean(lot({ lot_number: '1', est_resale_low: 40, est_resale_high: 70 }))).toBe(55);
  });
  it('uses the single present bound', () => {
    expect(resaleMean(lot({ lot_number: '1', est_resale_low: 40 }))).toBe(40);
    expect(resaleMean(lot({ lot_number: '2', est_resale_high: 80 }))).toBe(80);
  });
  it('is null when unvalued', () => {
    expect(resaleMean(lot({ lot_number: '1' }))).toBeNull();
  });
});

describe('formatMoney', () => {
  it('rounds and adds a thousands separator', () => {
    expect(formatMoney(54.5)).toBe('$55');
    expect(formatMoney(1200)).toBe('$1,200');
    expect(formatMoney(0)).toBe('$0');
  });
  it('renders a dash for null', () => {
    expect(formatMoney(null)).toBe('—');
  });
});

describe('resaleRange', () => {
  it('shows a full range', () => {
    expect(resaleRange(lot({ lot_number: '1', est_resale_low: 40, est_resale_high: 70 }))).toBe('$40–$70');
  });
  it('shows a one-sided bound', () => {
    expect(resaleRange(lot({ lot_number: '1', est_resale_low: 40 }))).toBe('≥ $40');
    expect(resaleRange(lot({ lot_number: '2', est_resale_high: 70 }))).toBe('≤ $70');
  });
});

describe('isPotentialResale (demand-aware)', () => {
  it('accepts good/fair outlook with medium/high confidence', () => {
    expect(isPotentialResale(valued('1', 40, 70, 'high', 'good'))).toBe(true);
    expect(isPotentialResale(valued('2', 40, 70, 'medium', 'fair'))).toBe(true);
  });
  it('rejects poor outlook even at high confidence (e.g. used shoes)', () => {
    expect(isPotentialResale(valued('3', 40, 70, 'high', 'poor'))).toBe(false);
  });
  it('rejects low confidence even with good outlook', () => {
    expect(isPotentialResale(valued('4', 40, 70, 'low', 'good'))).toBe(false);
  });
  it('rejects unvalued lots', () => {
    expect(isPotentialResale(lot({ lot_number: '5' }))).toBe(false);
  });
});

describe('confidencePasses', () => {
  it("'all' lets everything through, including unvalued", () => {
    expect(confidencePasses(lot({ lot_number: '1' }), 'all')).toBe(true);
    expect(confidencePasses(valued('2', 1, 2, 'low', 'good'), 'all')).toBe(true);
  });
  it("'high' admits only high", () => {
    expect(confidencePasses(valued('1', 1, 2, 'high', 'good'), 'high')).toBe(true);
    expect(confidencePasses(valued('2', 1, 2, 'medium', 'good'), 'high')).toBe(false);
    expect(confidencePasses(lot({ lot_number: '3' }), 'high')).toBe(false);
  });
  it("'medium-plus' admits medium and high, excludes low/unvalued", () => {
    expect(confidencePasses(valued('1', 1, 2, 'high', 'good'), 'medium-plus')).toBe(true);
    expect(confidencePasses(valued('2', 1, 2, 'medium', 'good'), 'medium-plus')).toBe(true);
    expect(confidencePasses(valued('3', 1, 2, 'low', 'good'), 'medium-plus')).toBe(false);
    expect(confidencePasses(lot({ lot_number: '4' }), 'medium-plus')).toBe(false);
  });
});

describe('filterLots: resale filters compose with the view', () => {
  const lots: Lot[] = [
    valued('a', 40, 70, 'high', 'good'), // potential, high
    valued('b', 40, 70, 'medium', 'fair'), // potential, medium
    valued('c', 40, 70, 'high', 'poor'), // high but poor → not potential
    valued('d', 40, 70, 'low', 'good'), // good but low → not potential
    lot({ lot_number: 'e' }), // unvalued
  ];
  const base = {
    tab: 'all' as const,
    dayFilter: 'Both' as const,
    categoryPath: [],
    batBucket: null,
    watched: new Set<string>(),
  };

  it('no resale filters → all lots', () => {
    const out = filterLots(lots, base);
    expect(out.map((l) => l.lot_number).sort()).toEqual(['a', 'b', 'c', 'd', 'e']);
  });

  it("confidence 'high' → only high-confidence valued lots", () => {
    const out = filterLots(lots, { ...base, confidenceFilter: 'high' });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['a', 'c']);
  });

  it("confidence 'medium-plus' → medium and high", () => {
    const out = filterLots(lots, { ...base, confidenceFilter: 'medium-plus' });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['a', 'b', 'c']);
  });

  it('potential resales → excludes poor outlook, low confidence, and unvalued', () => {
    const out = filterLots(lots, { ...base, potentialOnly: true });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['a', 'b']);
  });

  it('potential + high confidence compose (AND)', () => {
    const out = filterLots(lots, { ...base, potentialOnly: true, confidenceFilter: 'high' });
    expect(out.map((l) => l.lot_number).sort()).toEqual(['a']);
  });

  it('composes with the watched tab', () => {
    const out = filterLots(lots, {
      ...base,
      tab: 'watched',
      watched: new Set(['a', 'c']),
      potentialOnly: true,
    });
    // a is potential & watched; c is watched but poor outlook → excluded.
    expect(out.map((l) => l.lot_number)).toEqual(['a']);
  });
});
