import type { Lot, Condition, Confidence, ResaleOutlook } from './types';

/**
 * The presentation record the redesigned components consume.
 *
 * This is an explicit mapping, NOT a rename-in-place of `Lot`. The design
 * handoff (docs/design/README.md § "Data shape") assumes short, already-derived
 * field names, and our bundle disagrees with it in several ways that a rename
 * would paper over:
 *
 *  - `day` in the bundle is 'Sunday' or the EMPTY STRING (the Monday lots carry
 *    no day at all), so the day letter is derived from the lot-number prefix.
 *  - "Unvalued" resale reads as 0, never null, so a plain copy would render
 *    "$0" on lots the valuation pass could not price.
 *  - `est_retail_price` is 0 on 297 lots and null on 15, so mid/retail is an
 *    Infinity waiting to happen.
 *  - `match_strength` is the string 'none' on non-picks, not null.
 *
 * Filtering, sorting and search still operate on the raw `Lot` — this layer is
 * strictly for rendering, and every lot carries `src` back to its original.
 */
export interface LotView {
  /** Index in the source array. Drives the tile tint (i % 8). */
  i: number;
  /** lot_number, e.g. "S-1204". Unique across both auctions. */
  lot: string;
  title: string;
  cat: string;
  sub: string;
  /** First Bat's List bucket, or null when the lot isn't on the list. */
  bucket: string | null;
  buckets: string[];
  isBat: boolean;
  /** est_retail_price, with 0 and null both normalised to null. */
  retail: number | null;
  lo: number | null;
  hi: number | null;
  /** (lo + hi) / 2. Null when the lot has no usable resale figure. */
  mid: number | null;
  /** mid / retail. Null when either side is missing. */
  ratio: number | null;
  /** ratio >= the 90th percentile over the WHOLE set (see buildLotViews). */
  tick: boolean;
  cond: Condition | null;
  /** 'S' | 'M', derived from the lot-number prefix. */
  day: DayLetter;
  /** close_at as epoch ms, or null when the bundle carries no time. */
  closeMs: number | null;
  /** Free-form Bat's List level under `bucket`, e.g. 'scrub brushes'. */
  subtype: string | null;
  /** resale_confidence — lowercase 'low' | 'medium' | 'high'. */
  conf: Confidence | null;
  /**
   * resale_outlook — lowercase, and only THREE values: 'poor' | 'fair' | 'good'.
   * The design assumes a fourth ('Strong') that our resale pass never emits.
   */
  out: ResaleOutlook | null;
  pick: boolean;
  /** match_strength, with 'none' normalised to null. */
  strength: string | null;
  /** resale_reasoning. */
  note: string | null;
  /** personal_reasoning. */
  match: string | null;
  /** Grid tile image — the 350px thumb variant, not the sz=MAX original. */
  img: string | null;
  /** Full-size image, for the stage-2 detail overlay. */
  imgFull: string | null;
  url: string;
  /** Tile tint index, 0–7. */
  tint: number;
  /** The record this was mapped from. */
  src: Lot;
}

export type DayLetter = 'S' | 'M';

/** Top-decile threshold used for `tick`. */
export const TICK_PERCENTILE = 0.9;

/** 0 and null both mean "no figure" in this bundle. */
function positive(value: number | null | undefined): number | null {
  return typeof value === 'number' && value > 0 ? value : null;
}

/**
 * `close_at` as epoch milliseconds.
 *
 * A timestamp rather than a formatted string on purpose: this mapping runs
 * once over the whole bundle, but whether a lot has ENDED changes while you
 * are looking at it, so the comparison has to happen at render against a
 * ticking clock (see hooks/useNow.ts).
 */
export function closeMs(lot: Lot): number | null {
  if (!lot.close_at) return null;
  const ms = Date.parse(lot.close_at);
  return Number.isFinite(ms) ? ms : null;
}

/**
 * The compact card form: '1:04p'. Deliberately short — it sits beside the
 * condition word in a 13px row, and the date is redundant when the auction
 * runs on one or two known days (the S/M chip carries which).
 */
export function closeLabel(ms: number): string {
  const d = new Date(ms);
  let h = d.getHours();
  const suffix = h < 12 ? 'a' : 'p';
  h = h % 12 || 12;
  return `${h}:${String(d.getMinutes()).padStart(2, '0')}${suffix}`;
}

/** The detail overlay's long form: 'Sun 9 Aug, 1:04 PM'. */
export function closeLabelLong(ms: number): string {
  return new Date(ms).toLocaleString('en-US', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/**
 * The day letter. `lot.day` is unreliable — every Monday lot in the bundle has
 * an empty string — but the lot number is prefixed 'S-'/'M-' by the two-auction
 * combine step, on 100% of rows. Fall back to `lot.day` for single-auction
 * weeks, where lot numbers may carry no prefix.
 */
export function dayLetter(lot: Lot): DayLetter {
  if (lot.lot_number.startsWith('M-')) return 'M';
  if (lot.lot_number.startsWith('S-')) return 'S';
  return lot.day === 'Monday' ? 'M' : 'S';
}

/**
 * The representative resale figure. Mirrors `resaleMean` in lib/resale.ts, but
 * additionally treats a 0 bound as absent so unpriced lots render blank rather
 * than "$0" — with the nuance that a lot priced 0–20 still means 10, not 20.
 */
function resaleFigures(lot: Lot): { lo: number | null; hi: number | null; mid: number | null } {
  const rawLo = lot.est_resale_low;
  const rawHi = lot.est_resale_high;
  const hasAny = (rawLo ?? 0) > 0 || (rawHi ?? 0) > 0;
  if (!hasAny) return { lo: null, hi: null, mid: null };
  if (rawLo !== null && rawHi !== null) {
    return { lo: rawLo, hi: rawHi, mid: (rawLo + rawHi) / 2 };
  }
  const only = rawLo ?? rawHi;
  return { lo: rawLo, hi: rawHi, mid: only };
}

/** The value at the given percentile of an ascending-sorted sample. */
function percentile(sortedAsc: number[], p: number): number | null {
  if (sortedAsc.length === 0) return null;
  return sortedAsc[Math.floor(p * (sortedAsc.length - 1))];
}

/**
 * Map every lot to its presentation record.
 *
 * The one piece of cross-lot state is `tick`: the resale-to-retail ratio's 90th
 * percentile is computed ONCE over the whole set here, so "exceptional value"
 * means exceptional for the auction, not exceptional among whatever 12 lots a
 * filter happened to leave on screen. Lots with no ratio (no resale, or retail
 * missing/zero) are excluded from the sample rather than counted as zero.
 */
export function buildLotViews(lots: Lot[]): LotView[] {
  const views: LotView[] = lots.map((src, i) => {
    const { lo, hi, mid } = resaleFigures(src);
    const retail = positive(src.est_retail_price);
    const ratio = retail !== null && mid !== null ? mid / retail : null;
    const strength = src.match_strength && src.match_strength !== 'none' ? src.match_strength : null;

    return {
      i,
      lot: src.lot_number,
      title: src.title,
      cat: src.category,
      sub: src.subcategory,
      bucket: src.bat_buckets.length > 0 ? src.bat_buckets[0] : null,
      buckets: src.bat_buckets,
      isBat: src.is_bat,
      retail,
      lo,
      hi,
      mid,
      ratio,
      tick: false, // filled in below, once the threshold is known
      cond: src.condition,
      day: dayLetter(src),
      closeMs: closeMs(src),
      subtype: src.bat_subtype || null,
      conf: src.resale_confidence,
      out: src.resale_outlook,
      pick: src.personal_match === true,
      strength,
      note: src.resale_reasoning || null,
      match: src.personal_reasoning || null,
      img: src.thumb_url || src.image_url || null,
      imgFull: src.image_url || src.thumb_url || null,
      url: src.lot_url,
      tint: i % 8,
      src,
    };
  });

  const ratios: number[] = [];
  for (const v of views) {
    if (v.ratio !== null && Number.isFinite(v.ratio)) ratios.push(v.ratio);
  }
  ratios.sort((a, b) => a - b);
  const threshold = percentile(ratios, TICK_PERCENTILE);
  if (threshold !== null) {
    for (const v of views) {
      v.tick = v.ratio !== null && Number.isFinite(v.ratio) && v.ratio >= threshold;
    }
  }

  return views;
}

/** Index the views by lot number, for lookup from the filtered `Lot[]`. */
export function indexViews(views: LotView[]): Map<string, LotView> {
  return new Map(views.map((v) => [v.lot, v]));
}

/**
 * Condition owns the entire colour scale in the redesign — it is the only place
 * the five-step palette appears (docs/design/README.md § "The signal system").
 * Everything else is greyscale, lavender accent, or the blush filter chip.
 */
/**
 * The label text is HiBid's, 1:1; the colour stays a coarse five-step quality
 * signal, so several labels share a swatch. Anything absent here — an unmapped
 * condition, or one HiBid adds later — falls back to the neutral divider.
 */
export const CONDITION_COLOR: Record<string, string> = {
  'Brand New - Sealed': 'var(--c-new)',
  'Brand New - Open Box': 'var(--c-new)',
  'New (Adjusted Quantity)': 'var(--c-new)',
  'Best Before (Grocery)': 'var(--c-new)',
  Excellent: 'var(--c-like)',
  Good: 'var(--c-good)',
  'New With Defects': 'var(--c-fair)',
  Fair: 'var(--c-fair)',
  'Heavily Used': 'var(--c-heavy)',
  'For Parts Only': 'var(--c-heavy)',
  // Not a condition at all — HiBid uses it to mark lots that aren't real items
  // (fee notices, house announcements). Neutral so it never reads as quality.
  'Do Not Bid': 'var(--line)',
};

/** Condition colour, falling back to the neutral divider for unknown condition. */
export function conditionColor(cond: Condition | null): string {
  return (cond && CONDITION_COLOR[cond]) || 'var(--line)';
}

/** Display capitalisation for the lowercase confidence/outlook enums. */
export function titleCase(value: string | null): string | null {
  if (!value) return null;
  return value.charAt(0).toUpperCase() + value.slice(1);
}
