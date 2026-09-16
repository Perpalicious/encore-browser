import { describe, it, expect } from 'vitest';
import type { Bundle, HammerWeek, Lot } from './types';
import { lot } from '../test/lotFixture';
import {
  hammerDateLabel,
  hammerDetailFor,
  hammerFor,
  hammerLine,
  hammerRange,
  hammerWeeks,
} from './hammer';

function week(partial: Partial<HammerWeek> = {}): HammerWeek {
  return {
    close_date: '2026-09-13',
    sold: 6,
    unsold: 3,
    median: 14,
    low: 9,
    high: 22,
    ...partial,
  };
}

function bundle(lots: Lot[], hammer?: Bundle['hammer']): Bundle {
  return { lots, bucket_groups: {}, groups: [], hammer };
}

describe('hammerWeeks lookup', () => {
  const index = { 'SHARK|EXCELLENT': { weeks: [week()] } };

  it('resolves a lot through its hammer_key', () => {
    const weeks = hammerWeeks(lot({ lot_number: '1', hammer_key: 'SHARK|EXCELLENT' }), index);
    expect(weeks).toHaveLength(1);
    expect(weeks?.[0].median).toBe(14);
  });

  it('is null for a lot with no key, an unknown key, or an empty history', () => {
    expect(hammerWeeks(lot({ lot_number: '1' }), index)).toBeNull();
    expect(hammerWeeks(lot({ lot_number: '2', hammer_key: null }), index)).toBeNull();
    expect(hammerWeeks(lot({ lot_number: '3', hammer_key: 'NOPE|' }), index)).toBeNull();
    expect(
      hammerWeeks(lot({ lot_number: '4', hammer_key: 'X|' }), { 'X|': { weeks: [] } })
    ).toBeNull();
  });

  it('is null on a bundle built without --hammer, where the map is absent', () => {
    // This is the live site's state until Bat runs the pull, so it has to be
    // the quiet case rather than a crash.
    const l = lot({ lot_number: '1', hammer_key: 'SHARK|EXCELLENT' });
    expect(hammerWeeks(l, undefined)).toBeNull();
    expect(hammerFor(l, bundle([l]))).toBeNull();
    expect(hammerFor(l, null)).toBeNull();
  });

  it('reads the map off a whole bundle', () => {
    const l = lot({ lot_number: '1', hammer_key: 'SHARK|EXCELLENT' });
    expect(hammerFor(l, bundle([l], index))?.[0].sold).toBe(6);
  });
});

describe('hammerLine', () => {
  it('reads "Sold 6× · med $14 · $9–$22 · 3 unsold" at full detail', () => {
    expect(hammerLine(week())).toBe('Sold 6× · med $14 · $9–$22 · 3 unsold');
  });

  it('drops the range first, then the unsold count, as width runs out', () => {
    expect(hammerLine(week(), 'no-range')).toBe('Sold 6× · med $14 · 3 unsold');
    expect(hammerLine(week(), 'minimal')).toBe('Sold 6× · med $14');
  });

  it('says how many were listed when nothing sold, never "$0"', () => {
    // A zero-bid lot has no price at all — the ladder starts at the opening
    // bid — so it is counted as unsold and never priced.
    const line = hammerLine(week({ sold: 0, unsold: 12, median: null, low: null, high: null }));
    expect(line).toBe('Listed 12× · none sold');
    expect(line).not.toContain('$');
  });

  it('omits the unsold clause when everything sold', () => {
    expect(hammerLine(week({ unsold: 0 }))).toBe('Sold 6× · med $14 · $9–$22');
  });

  it('omits the range on a single sale, where it only repeats the median', () => {
    expect(hammerLine(week({ sold: 1, unsold: 0, low: 14, high: 14 }))).toBe(
      'Sold 1× · med $14'
    );
  });

  it('collapses a range whose bounds are equal', () => {
    expect(hammerRange(week({ low: 14, high: 14 }))).toBe('$14');
    expect(hammerRange(week({ low: null, high: null }))).toBeNull();
    expect(hammerRange(week({ low: 9, high: null }))).toBe('$9');
  });
});

describe('hammerDetailFor', () => {
  it('gives the full line only to a wide column', () => {
    expect(hammerDetailFor(260)).toBe('full');
    expect(hammerDetailFor(196)).toBe('no-range'); // standard density
    expect(hammerDetailFor(150)).toBe('minimal'); // compact density
  });
});

describe('hammerDateLabel', () => {
  it('shortens a close date for the detail table', () => {
    expect(hammerDateLabel('2026-09-13')).toBe('Sep 13');
  });

  it('passes an unparseable date through rather than rendering "Invalid Date"', () => {
    expect(hammerDateLabel('whenever')).toBe('whenever');
  });
});
