import { describe, it, expect } from 'vitest';
import { computeGeometry, LIST_ROW_H, TOUCH_ROW_H, LID_H, TEXT_H } from './useGridGeometry';
import type { GeometryOptions } from './useGridGeometry';

const base: GeometryOptions = {
  density: 'standard',
  mobile: false,
  coarse: false,
  rows: false,
  mobileCols: 3,
};

/** Columns laid out at `width`, in the given density. */
const colsAt = (width: number, density: 'standard' | 'compact' = 'standard') =>
  computeGeometry(width, 900, { ...base, density }).cols;

describe('desktop column count', () => {
  it('stops at 6 in standard density however wide the window gets', () => {
    expect(colsAt(1440)).toBe(6);
    expect(colsAt(2140)).toBe(6);
    expect(colsAt(4000)).toBe(6);
  });

  it('lets compact go to 8 — that is what the density toggle is for', () => {
    expect(colsAt(1440, 'compact')).toBe(8);
    expect(colsAt(2140, 'compact')).toBe(8);
    expect(colsAt(4000, 'compact')).toBe(8);
  });

  it('still computes from the container below the ceiling, with no breakpoints', () => {
    // 196px target + 12px gap: the count climbs one column at a time.
    expect(colsAt(700)).toBe(3);
    expect(colsAt(900)).toBe(4);
    expect(colsAt(1100)).toBe(5);
  });

  it('never drops below 2, however narrow', () => {
    expect(colsAt(320)).toBe(2);
    expect(colsAt(100)).toBe(2);
  });

  it('keeps the card square-plus-text identity: rowH = colW + lid + text + gap', () => {
    const g = computeGeometry(1440, 900, base);
    expect(g.cols).toBe(6);
    expect(g.rowH).toBeCloseTo(g.colW + LID_H + TEXT_H + g.gap, 5);
    // Six columns and two 16px pads must account for the full width.
    expect(g.colW * g.cols + g.gap * (g.cols - 1) + g.padX * 2).toBeCloseTo(1440, 5);
  });
});

describe('row modes are unaffected by the ceiling', () => {
  it('is always one full-width column', () => {
    const g = computeGeometry(2140, 900, { ...base, rows: true });
    expect(g.cols).toBe(1);
    expect(g.rowH).toBe(LIST_ROW_H);
    expect(g.mode).toBe('lrow');
  });

  it('uses the taller row under a coarse pointer', () => {
    expect(computeGeometry(2140, 900, { ...base, rows: true, coarse: true }).rowH).toBe(
      TOUCH_ROW_H
    );
  });
});

describe('mobile', () => {
  it('takes its column count from the stepper, not the ceiling', () => {
    for (const mobileCols of [2, 3, 4] as const) {
      expect(computeGeometry(390, 844, { ...base, mobile: true, mobileCols }).cols).toBe(
        mobileCols
      );
    }
  });
});
