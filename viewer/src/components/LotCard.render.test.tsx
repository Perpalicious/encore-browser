import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Lot } from '../lib/types';
import { LotCard } from './LotCard';
import { LotExpandPanel } from './LotExpandPanel';

const noop = () => {};

function lot(partial: Partial<Lot> & { lot_number: string }): Lot {
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

function renderCard(l: Lot): string {
  return renderToStaticMarkup(
    <LotCard
      lot={l}
      expanded={false}
      onToggleExpand={noop}
      watched={false}
      onToggleWatch={noop}
      density="standard"
    />
  );
}

describe('LotCard resale summary', () => {
  it('renders resale + retail when the lot is valued', () => {
    const html = renderCard(
      lot({ lot_number: '1', est_resale_low: 40, est_resale_high: 70, est_retail_price: 120 })
    );
    expect(html).toContain('data-testid="resale-summary"');
    expect(html).toContain('Resale');
    expect(html).toContain('~$55'); // mean of 40 and 70
    expect(html).toContain('Retail');
    expect(html).toContain('$120');
  });

  it('omits the resale row entirely when the lot is not valued', () => {
    const html = renderCard(lot({ lot_number: '2', est_retail_price: 120 }));
    expect(html).not.toContain('data-testid="resale-summary"');
    expect(html).not.toContain('Resale');
  });
});

describe('LotExpandPanel resale detail', () => {
  it('renders range, confidence, outlook, and reasoning when valued', () => {
    const html = renderToStaticMarkup(
      <LotExpandPanel
        lot={lot({
          lot_number: '1',
          est_resale_low: 40,
          est_resale_high: 70,
          est_retail_price: 120,
          resale_confidence: 'medium',
          resale_outlook: 'good',
          resale_reasoning: 'Comparable units resell steadily.',
        })}
        onCollapse={noop}
        fullRow
      />
    );
    expect(html).toContain('data-testid="resale-detail"');
    expect(html).toContain('$40–$70'); // range
    expect(html).toContain('medium confidence');
    expect(html).toContain('good outlook');
    expect(html).toContain('Comparable units resell steadily.');
  });

  it('omits the resale detail when not valued', () => {
    const html = renderToStaticMarkup(
      <LotExpandPanel lot={lot({ lot_number: '2' })} onCollapse={noop} fullRow />
    );
    expect(html).not.toContain('data-testid="resale-detail"');
  });
});
