import type { Lot } from '../lib/types';
import { buildLotViews, type LotView } from '../lib/lotView';

/**
 * A minimal valid Lot for render tests. Every optional field defaults to the
 * "absent" shape so a test only has to state what it actually cares about.
 */
export function lot(partial: Partial<Lot> & { lot_number: string }): Lot {
  return {
    day: 'Sunday',
    title: `Lot ${partial.lot_number}`,
    description: 'A thing.',
    condition: 'Good',
    thumb_url: '',
    image_url: '',
    lot_url: 'https://encoreauctions.hibid.com/lot/1/x',
    category: 'Tools',
    subcategory: 'Hand Tools',
    category_path: ['Tools', 'Hand Tools'],
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

/** The same fixture, mapped through the real presentation layer. */
export function lotView(partial: Partial<Lot> & { lot_number: string }): LotView {
  return buildLotViews([lot(partial)])[0];
}
