import { describe, it, expect } from 'vitest';
import { normalize, buildSearchIndex, fuzzyMatchLotNumbers, SEARCH_THRESHOLD } from './search';
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

describe('fuzzy search', () => {
  const lots: Lot[] = [
    lot({ lot_number: '1', title: 'Wüsthof Classic Chef Knife 8-inch' }),
    lot({ lot_number: '2', title: 'DEWALT 20V MAX Cordless Drill' }),
    lot({ lot_number: '3', title: 'KitchenAid Artisan Stand Mixer' }),
    lot({ lot_number: '4', title: 'Generic Plastic Spoon Set', category_path: ['Kitchen', 'Utensils'] }),
  ];
  const fuse = buildSearchIndex(lots);

  it('matches an accented brand from an unaccented typo query (wustof → Wüsthof)', () => {
    const matches = fuzzyMatchLotNumbers(fuse, 'wustof');
    expect(matches.has('1')).toBe(true);
  });

  it('tolerates a multi-word typo (dewalt drll → DEWALT ... Drill)', () => {
    const matches = fuzzyMatchLotNumbers(fuse, 'dewalt drll');
    expect(matches.has('2')).toBe(true);
  });

  it('tolerates a single missing letter (kitchenad → KitchenAid)', () => {
    const matches = fuzzyMatchLotNumbers(fuse, 'kitchenad');
    expect(matches.has('3')).toBe(true);
  });

  it('searches across category_path levels', () => {
    const matches = fuzzyMatchLotNumbers(fuse, 'utensils');
    expect(matches.has('4')).toBe(true);
  });

  it('returns an empty set for a blank query', () => {
    expect(fuzzyMatchLotNumbers(fuse, '   ').size).toBe(0);
  });

  it('exposes an adjustable threshold constant', () => {
    expect(SEARCH_THRESHOLD).toBeGreaterThan(0);
    expect(SEARCH_THRESHOLD).toBeLessThan(1);
  });
});
