import { describe, it, expect } from 'vitest';
import type { Lot } from './types';
import { buildLotViews, indexViews, dayLetter, conditionColor, titleCase } from './lotView';

function lot(partial: Partial<Lot> & { lot_number: string }): Lot {
  return {
    day: 'Sunday',
    title: `Lot ${partial.lot_number}`,
    description: '',
    condition: 'Good',
    thumb_url: 'https://cdn.example/img?id=1&h=350&w=350',
    image_url: 'https://cdn.example/img?id=1',
    lot_url: 'https://encoreauctions.hibid.com/lot/1/x',
    category: 'Tools',
    subcategory: 'Hand Tools',
    category_path: ['Tools', 'Hand Tools'],
    is_bat: false,
    bat_buckets: [],
    confidence: 'low',
    est_retail_price: 100,
    est_resale_low: 40,
    est_resale_high: 60,
    resale_confidence: 'high',
    resale_outlook: 'fair',
    resale_reasoning: 'Sells steadily.',
    ...partial,
  };
}

function view(partial: Partial<Lot> & { lot_number: string }) {
  return buildLotViews([lot(partial)])[0];
}

describe('buildLotViews field mapping', () => {
  it('maps our field names onto the design record', () => {
    const v = view({
      lot_number: 'S-1204',
      title: 'Cordless drill',
      category: 'Tools',
      subcategory: 'Power Tools',
      is_bat: true,
      bat_buckets: ['Power tools', 'Garage'],
      est_retail_price: 100,
      est_resale_low: 40,
      est_resale_high: 60,
      resale_confidence: 'medium',
      resale_outlook: 'good',
      resale_reasoning: 'Steady demand.',
      personal_match: true,
      personal_reasoning: 'Matches the workshop interest.',
    });

    expect(v.lot).toBe('S-1204');
    expect(v.title).toBe('Cordless drill');
    expect(v.cat).toBe('Tools');
    expect(v.sub).toBe('Power Tools');
    expect(v.bucket).toBe('Power tools');
    expect(v.buckets).toEqual(['Power tools', 'Garage']);
    expect(v.isBat).toBe(true);
    expect(v.retail).toBe(100);
    expect(v.lo).toBe(40);
    expect(v.hi).toBe(60);
    expect(v.mid).toBe(50);
    expect(v.conf).toBe('medium');
    expect(v.out).toBe('good');
    expect(v.pick).toBe(true);
    expect(v.note).toBe('Steady demand.');
    expect(v.match).toBe('Matches the workshop interest.');
  });

  it('uses the 350px thumb for the tile and keeps the full-size image separately', () => {
    const v = view({ lot_number: 'S-1' });
    expect(v.img).toBe('https://cdn.example/img?id=1&h=350&w=350');
    expect(v.imgFull).toBe('https://cdn.example/img?id=1');
  });

  it('falls back between the two image URLs and reports null when both are empty', () => {
    expect(view({ lot_number: 'S-1', thumb_url: '' }).img).toBe('https://cdn.example/img?id=1');
    expect(view({ lot_number: 'S-1', thumb_url: '', image_url: '' }).img).toBeNull();
    expect(view({ lot_number: 'S-1', thumb_url: '', image_url: '' }).imgFull).toBeNull();
  });

  it('has no bucket when the lot is not on Bat’s List', () => {
    expect(view({ lot_number: 'S-1' }).bucket).toBeNull();
  });

  it('assigns tile tints by index, cycling every 8', () => {
    const views = buildLotViews(
      Array.from({ length: 10 }, (_, i) => lot({ lot_number: `S-${i}` }))
    );
    expect(views.map((v) => v.tint)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 0, 1]);
  });
});

describe('day derivation', () => {
  it('reads the day from the lot-number prefix, not the day field', () => {
    // Every Monday lot in the real bundle carries an EMPTY day string; only the
    // prefix is reliable on two-auction weeks.
    expect(dayLetter(lot({ lot_number: 'M-31144', day: '' }))).toBe('M');
    expect(dayLetter(lot({ lot_number: 'S-11834', day: 'Sunday' }))).toBe('S');
    expect(dayLetter(lot({ lot_number: 'M-1', day: 'Sunday' }))).toBe('M');
  });

  it('falls back to the day field on single-auction weeks with no prefix', () => {
    expect(dayLetter(lot({ lot_number: '1204', day: 'Monday' }))).toBe('M');
    expect(dayLetter(lot({ lot_number: '1204', day: 'Sunday' }))).toBe('S');
    expect(dayLetter(lot({ lot_number: '1204', day: '' }))).toBe('S');
  });

  it('handles the letter-suffixed split lots', () => {
    expect(view({ lot_number: 'S-1a' }).day).toBe('S');
    expect(view({ lot_number: 'M-1c' }).day).toBe('M');
  });
});

describe('resale and retail normalisation', () => {
  it('treats a 0/0 range as no resale data at all', () => {
    const v = view({ lot_number: 'S-1', est_resale_low: 0, est_resale_high: 0 });
    expect(v.lo).toBeNull();
    expect(v.hi).toBeNull();
    expect(v.mid).toBeNull();
    expect(v.ratio).toBeNull();
  });

  it('keeps a 0 low bound when the high bound is real', () => {
    // 0–20 means a mid of 10, not 20: dropping the zero bound would inflate it.
    const v = view({ lot_number: 'S-1', est_resale_low: 0, est_resale_high: 20 });
    expect(v.lo).toBe(0);
    expect(v.hi).toBe(20);
    expect(v.mid).toBe(10);
  });

  it('handles nulls on either bound', () => {
    expect(view({ lot_number: 'S-1', est_resale_low: null }).mid).toBe(60);
    expect(view({ lot_number: 'S-1', est_resale_high: null }).mid).toBe(40);
    expect(view({ lot_number: 'S-1', est_resale_low: null, est_resale_high: null }).mid).toBeNull();
  });

  it('normalises a 0 or null retail price to null, so no ratio is Infinity', () => {
    for (const retail of [0, null]) {
      const v = view({ lot_number: 'S-1', est_retail_price: retail });
      expect(v.retail).toBeNull();
      expect(v.ratio).toBeNull();
      expect(v.tick).toBe(false);
    }
  });

  it('computes the ratio from the mid, not from either bound', () => {
    const v = view({
      lot_number: 'S-1',
      est_resale_low: 40,
      est_resale_high: 60,
      est_retail_price: 200,
    });
    expect(v.ratio).toBeCloseTo(0.25);
  });
});

describe('tick (top-decile resale-to-retail spread)', () => {
  const spread = (n: number, resale: number) =>
    lot({
      lot_number: `S-${n}`,
      est_resale_low: resale,
      est_resale_high: resale,
      est_retail_price: 100,
    });

  it('flags only the top decile of the whole set', () => {
    // Ratios 0.01 … 0.20 over 20 lots; the 90th percentile lands at 0.18.
    const views = buildLotViews(Array.from({ length: 20 }, (_, i) => spread(i, i + 1)));
    const ticked = views.filter((v) => v.tick).map((v) => v.lot);
    expect(ticked).toEqual(['S-17', 'S-18', 'S-19']);
  });

  it('is computed over the whole set, so filtering cannot change it', () => {
    const all = Array.from({ length: 20 }, (_, i) => spread(i, i + 1));
    const whole = buildLotViews(all);
    const wholeTicked = new Set(whole.filter((v) => v.tick).map((v) => v.lot));

    // The same lots re-mapped from a narrowed set would move the threshold —
    // which is exactly why the mapping runs once, over `allLots`, at load.
    const narrowed = buildLotViews(all.slice(0, 5));
    const narrowedTicked = new Set(narrowed.filter((v) => v.tick).map((v) => v.lot));
    expect(narrowedTicked).not.toEqual(wholeTicked);
    expect(wholeTicked.has('S-19')).toBe(true);
    expect(wholeTicked.has('S-4')).toBe(false);
  });

  it('excludes lots with no ratio from the sample rather than counting them as zero', () => {
    const views = buildLotViews([
      ...Array.from({ length: 10 }, (_, i) => spread(i, i + 1)),
      lot({ lot_number: 'S-noretail', est_retail_price: 0 }),
      lot({ lot_number: 'S-noresale', est_resale_low: 0, est_resale_high: 0 }),
    ]);
    const byLot = indexViews(views);
    expect(byLot.get('S-noretail')!.tick).toBe(false);
    expect(byLot.get('S-noresale')!.tick).toBe(false);
    // The threshold still comes from the 10 lots that do have a ratio: the
    // 90th percentile of those is 0.09, so the top two clear it. Had the two
    // ratio-less lots been counted as 0, the threshold would have shifted down.
    expect(views.filter((v) => v.tick).map((v) => v.lot)).toEqual(['S-8', 'S-9']);
  });

  it('flags nothing when no lot has a usable ratio', () => {
    const views = buildLotViews([
      lot({ lot_number: 'S-1', est_retail_price: null }),
      lot({ lot_number: 'S-2', est_resale_low: 0, est_resale_high: 0 }),
    ]);
    expect(views.every((v) => !v.tick)).toBe(true);
  });
});

describe('personal-match normalisation', () => {
  it('is a pick only when personal_match is exactly true', () => {
    expect(view({ lot_number: 'S-1', personal_match: true }).pick).toBe(true);
    expect(view({ lot_number: 'S-1', personal_match: false }).pick).toBe(false);
    expect(view({ lot_number: 'S-1', personal_match: null }).pick).toBe(false);
    expect(view({ lot_number: 'S-1' }).pick).toBe(false); // older bundle
  });

  it("maps the 'none' strength sentinel to null", () => {
    // Non-picks carry the string 'none', not null — rendering it unguarded
    // would print "none match".
    expect(view({ lot_number: 'S-1', match_strength: 'none' }).strength).toBeNull();
    expect(view({ lot_number: 'S-1', match_strength: 'strong' }).strength).toBe('strong');
    expect(view({ lot_number: 'S-1' }).strength).toBeNull();
  });

  it('reports empty reasoning strings as null', () => {
    expect(view({ lot_number: 'S-1', personal_reasoning: '' }).match).toBeNull();
    expect(view({ lot_number: 'S-1', resale_reasoning: '' }).note).toBeNull();
  });
});

describe('outlook and confidence', () => {
  it('passes the three outlook values through unchanged', () => {
    // The handoff assumes a fourth value ('Strong') that our resale pass does
    // not emit. Nothing here invents one.
    expect(view({ lot_number: 'S-1', resale_outlook: 'poor' }).out).toBe('poor');
    expect(view({ lot_number: 'S-1', resale_outlook: 'fair' }).out).toBe('fair');
    expect(view({ lot_number: 'S-1', resale_outlook: 'good' }).out).toBe('good');
  });

  it('capitalises for display only', () => {
    expect(titleCase('good')).toBe('Good');
    expect(titleCase('medium')).toBe('Medium');
    expect(titleCase(null)).toBeNull();
  });
});

describe('condition colour', () => {
  it('maps each condition to its own token', () => {
    const colors = (['New', 'Like New', 'Good', 'Fair', 'Heavily Used'] as const).map(
      conditionColor
    );
    expect(new Set(colors).size).toBe(5);
    expect(conditionColor('New')).toBe('var(--c-new)');
    expect(conditionColor('Heavily Used')).toBe('var(--c-heavy)');
  });

  it('falls back to the neutral divider when condition is missing', () => {
    expect(conditionColor(null)).toBe('var(--line)');
  });
});

describe('indexViews', () => {
  it('keys the views by lot number', () => {
    const views = buildLotViews([lot({ lot_number: 'S-1' }), lot({ lot_number: 'M-2' })]);
    const byLot = indexViews(views);
    expect(byLot.get('S-1')!.day).toBe('S');
    expect(byLot.get('M-2')!.day).toBe('M');
    expect(byLot.get('nope')).toBeUndefined();
  });
});
