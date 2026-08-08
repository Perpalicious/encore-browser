import { useState, useEffect, type RefObject } from 'react';
import type { Density, MobileCols } from '../lib/types';

/**
 * Grid geometry — docs/design/README.md § "Desktop grid" and § "Mobile".
 *
 * In card modes the column count is COMPUTED from the container's width, not
 * chosen by breakpoint. That removes the old duplication where a hook and a
 * Tailwind `grid-cols-*` string both had to be edited in step (and silently
 * disagreed at any width Tailwind's breakpoints didn't line up with), and it
 * gives the virtualiser one uniform row height to work from.
 *
 * Row modes are simply one full-width column at a fixed height.
 *
 * The density control survives the redesign by choosing the target column
 * width: standard is the handoff's 196px (~6 columns at 1440), compact packs to
 * 150px (~8 columns). Each density also has a hard column ceiling, so a wide
 * monitor gets bigger cards rather than more of them. On mobile the 2/3/4
 * stepper sets the count directly.
 */

/** What the grid is laying out. Row heights differ per mode. */
export type LayoutMode = 'card' | 'lrow' | 'mrow';

export interface GridGeometry {
  mode: LayoutMode;
  /** Columns. 1 in row modes; in card modes 2–6 standard, 2–8 compact. */
  cols: number;
  /** Exact column width in px. */
  colW: number;
  /** Uniform row height: tile + condition lid + text block + gap, or the row. */
  rowH: number;
  gap: number;
  padX: number;
  /** Measured width of the scroll container, 0 before the first measurement. */
  width: number;
  /** Measured height of the scroll container — the virtualiser's viewport. */
  vh: number;
}

export const GRID_PAD_X = 16;
/** Height of the condition lid under the image tile. */
export const LID_H = 2;
/**
 * Height of the card's text block. Applied to the block as a hard height, so
 * `rowH` below is exact by construction rather than by arithmetic that a font
 * metric could quietly invalidate.
 *
 * NOTE: the handoff gives 63 here, but its own card markup does not fit in 63 —
 * 8px top padding + a 33px two-line title + 4px gap + a 13px figure row + 4px
 * gap + a 12px meta row + 9px bottom padding is 83. Every one of those element
 * specs is called final in the handoff, so the derived constant is what gives:
 * 63 would clip the retail/bucket row, and leaving the block auto-height would
 * make the rendered rows ~20px taller than the pitch the scrollbar is sized
 * from, which is exactly the drift the README warns about.
 */
export const TEXT_H = 83;
/** The three text-block rows, fixed so the block's height is deterministic. */
export const TITLE_H = 33;
export const FIGURE_ROW_H = 13;
export const META_ROW_H = 12;

/** Row heights: desktop list, the same rows under a coarse pointer, mobile. */
export const LIST_ROW_H = 67;
export const TOUCH_ROW_H = 78;

const MIN_COLS = 2;

/**
 * Column ceiling. Without one, a wide monitor just keeps adding columns —
 * a 2140px window laid out 9, and at that point the card is too small to read
 * a title from across a desk. Standard tops out at 6; compact is the
 * "more per screen" mode, so it is allowed 8.
 */
function maxCols(density: Density): number {
  return density === 'compact' ? 8 : 6;
}

export interface GeometryOptions {
  density: Density;
  /** True below 760px — the mobile layout. */
  mobile: boolean;
  /** True on a touch device: taller rows and bigger hit areas. */
  coarse: boolean;
  /** Rows instead of cards (desktop list view, or mobile rows mode). */
  rows: boolean;
  /** Mobile card column count, from the 2/3/4 stepper. */
  mobileCols: MobileCols;
}

function targetColWidth(density: Density): number {
  return density === 'compact' ? 150 : 196;
}

/** Card gap tightens as mobile columns grow, per the handoff. */
function cardGap(mobile: boolean, mobileCols: MobileCols): number {
  if (!mobile) return 12;
  return mobileCols === 4 ? 6 : mobileCols === 3 ? 8 : 10;
}

/**
 * Card text-block height by mobile column count: the bucket/retail row is
 * dropped at 3-up, and at 4-up the figures move onto the image entirely.
 */
export function textBlockHeight(mobile: boolean, mobileCols: MobileCols): number {
  if (!mobile) return TEXT_H;
  if (mobileCols === 4) return 33;
  if (mobileCols === 3) return 48;
  return TEXT_H;
}

export function computeGeometry(
  width: number,
  vh: number,
  { density, mobile, coarse, rows, mobileCols }: GeometryOptions
): GridGeometry {
  if (rows) {
    const rowH = mobile ? TOUCH_ROW_H : coarse ? TOUCH_ROW_H : LIST_ROW_H;
    return {
      mode: mobile ? 'mrow' : 'lrow',
      cols: 1,
      colW: width,
      rowH,
      gap: 0,
      padX: 0,
      width,
      vh,
    };
  }

  const gap = cardGap(mobile, mobileCols);
  const padX = GRID_PAD_X;
  const inner = Math.max(0, width - padX * 2);
  let cols: number;
  if (mobile) {
    cols = mobileCols;
  } else {
    const target = targetColWidth(density);
    cols = Math.max(
      MIN_COLS,
      Math.min(maxCols(density), Math.floor((inner + gap) / (target + gap)))
    );
  }
  const colW = Math.max(1, (inner - gap * (cols - 1)) / cols);
  const textH = textBlockHeight(mobile, mobileCols);
  return { mode: 'card', cols, colW, rowH: colW + LID_H + textH + gap, gap, padX, width, vh };
}

/**
 * Measure `ref` and derive the grid geometry from it. A ResizeObserver catches
 * container-only changes (a sidebar opening, the scrollbar appearing); the
 * window listener is the fallback for browsers that fire neither.
 */
export function useGridGeometry(
  ref: RefObject<HTMLElement>,
  options: GeometryOptions
): GridGeometry {
  const [size, setSize] = useState({ width: 0, vh: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const measure = () => {
      const width = el.clientWidth;
      const vh = el.clientHeight;
      setSize((prev) => (prev.width === width && prev.vh === vh ? prev : { width, vh }));
    };
    measure();

    const observer =
      typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    observer?.observe(el);
    window.addEventListener('resize', measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [ref]);

  return computeGeometry(size.width, size.vh, options);
}
