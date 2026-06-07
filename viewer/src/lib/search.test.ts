import { describe, it, expect } from 'vitest';
import {
  normalize,
  buildSearchIndex,
  exactMatchLotNumbers,
  fuzzyMatchLotNumbers,
  searchLotNumbers,
  SEARCH_THRESHOLD,
} from './search';
import type { Lot } from './types';

function lot(partial: Partial<Lot> & { lot_number: string; title: string }): Lot {
  return {
    day: 'Sunday',
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

describe('normalize', () => {
  it('folds Latin diacritics and lowercases', () => {
    expect(normalize('Wüsthof')).toBe('wusthof');
    expect(normalize('CRÈME BRÛLÉE')).toBe('creme brulee');
    expect(normalize('Piñata')).toBe('pinata');
  });
});

const LOTS: Lot[] = [
  lot({ lot_number: '1', title: 'Wüsthof Classic Chef Knife 8-inch' }),
  lot({ lot_number: '2', title: 'DEWALT 20V MAX Cordless Drill' }),
  lot({ lot_number: '3', title: 'KitchenAid Artisan Stand Mixer' }),
  lot({
    lot_number: '4',
    title: 'Generic Plastic Spoon Set',
    category_path: ['Kitchen', 'Utensils'],
    description: 'Set of six spoons; includes a colander.',
  }),
];
const index = buildSearchIndex(LOTS);

describe('exact search (default mode)', () => {
  it('matches a real substring and ONLY true matches (dewalt)', () => {
    const m = exactMatchLotNumbers(index, 'dewalt');
    expect([...m]).toEqual(['2']);
  });

  it('returns nothing for a typo that is not a real substring (wustof)', () => {
    expect(exactMatchLotNumbers(index, 'wustof').size).toBe(0);
  });

  it('is diacritic-insensitive for real substrings (wusthof → Wüsthof)', () => {
    expect(exactMatchLotNumbers(index, 'wusthof').has('1')).toBe(true);
  });

  it('AND-matches multi-word queries (cordless drill)', () => {
    expect([...exactMatchLotNumbers(index, 'cordless drill')]).toEqual(['2']);
    // A token absent from the lot rules it out.
    expect(exactMatchLotNumbers(index, 'cordless mixer').size).toBe(0);
  });

  it('still covers description and category_path', () => {
    expect(exactMatchLotNumbers(index, 'colander').has('4')).toBe(true); // description
    expect(exactMatchLotNumbers(index, 'utensils').has('4')).toBe(true); // category_path
  });

  it('returns an empty set for a blank query', () => {
    expect(exactMatchLotNumbers(index, '   ').size).toBe(0);
  });
});

describe('fuzzy search (opt-in mode)', () => {
  it('matches an accented brand from an unaccented typo (wustof → Wüsthof)', () => {
    expect(fuzzyMatchLotNumbers(index, 'wustof').has('1')).toBe(true);
  });

  it('tolerates a multi-word typo (dewalt cordles → DEWALT ... Cordless)', () => {
    expect(fuzzyMatchLotNumbers(index, 'dewalt cordles').has('2')).toBe(true);
  });

  it('is strict enough that a 1-error typo in a tiny token does not match (drll)', () => {
    // At threshold 0.2, an error in a ≤4-char token scores ~0.25 > 0.2 and is
    // intentionally rejected — this is the tightening, not a regression.
    expect(fuzzyMatchLotNumbers(index, 'drll').has('2')).toBe(false);
  });

  it('tolerates a single missing letter (kitchenad → KitchenAid)', () => {
    expect(fuzzyMatchLotNumbers(index, 'kitchenad').has('3')).toBe(true);
  });

  it('still finds description / category_path matches via substring union', () => {
    expect(fuzzyMatchLotNumbers(index, 'colander').has('4')).toBe(true); // description
    expect(fuzzyMatchLotNumbers(index, 'utensils').has('4')).toBe(true); // category_path
  });

  it('returns an empty set for a blank query', () => {
    expect(fuzzyMatchLotNumbers(index, '   ').size).toBe(0);
  });
});

describe('searchLotNumbers dispatch (the toggle)', () => {
  it('exact mode (fuzzy=false) rejects the typo that fuzzy mode accepts', () => {
    expect(searchLotNumbers(index, 'wustof', false).size).toBe(0);
    expect(searchLotNumbers(index, 'wustof', true).has('1')).toBe(true);
  });

  it('both modes agree on a real substring (dewalt)', () => {
    expect(searchLotNumbers(index, 'dewalt', false).has('2')).toBe(true);
    expect(searchLotNumbers(index, 'dewalt', true).has('2')).toBe(true);
  });
});

describe('threshold constant', () => {
  it('is adjustable and tightened below the old 0.3', () => {
    expect(SEARCH_THRESHOLD).toBeGreaterThan(0);
    expect(SEARCH_THRESHOLD).toBeLessThanOrEqual(0.2);
  });
});
