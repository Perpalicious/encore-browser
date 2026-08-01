import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Lot } from '../lib/types';
import { buildLotViews } from '../lib/lotView';
import { lot } from '../test/lotFixture';
import { LotCard } from './LotCard';

const noop = () => {};

/** Render a card through the real mapping layer, as the grid does. */
function renderCard(l: Lot): string {
  const [view] = buildLotViews([l]);
  return renderToStaticMarkup(
    <LotCard
      view={view}
      colW={196}
      textH={83}
      expanded={false}
      onToggleExpand={noop}
      watched={false}
      onToggleWatch={noop}
    />
  );
}

describe('LotCard resale summary', () => {
  it('renders the resale mean and the retail figure when the lot is valued', () => {
    const html = renderCard(
      lot({ lot_number: '1', est_resale_low: 40, est_resale_high: 70, est_retail_price: 120 })
    );
    expect(html).toContain('data-testid="resale-summary"');
    expect(html).toContain('$55'); // mean of 40 and 70
    expect(html).toContain('$120');
    // Money is greyscale and unlabelled in the redesign — size and weight carry
    // the distinction, so the "Resale"/"Retail" words are deliberately gone.
    expect(html).not.toContain('Resale');
    expect(html).not.toContain('Retail');
  });

  it('omits the resale figure entirely when the lot is not valued', () => {
    const html = renderCard(lot({ lot_number: '2', est_retail_price: 120 }));
    expect(html).not.toContain('data-testid="resale-summary"');
    expect(html).toContain('$120'); // retail still shows
  });

  it('treats a 0 resale range as unvalued rather than printing $0', () => {
    const html = renderCard(
      lot({ lot_number: '3', est_resale_low: 0, est_resale_high: 0, est_retail_price: 120 })
    );
    expect(html).not.toContain('data-testid="resale-summary"');
    expect(html).not.toContain('$0');
  });

  it('omits retail when it is 0 or null, without disturbing resale', () => {
    for (const retail of [0, null]) {
      const html = renderCard(
        lot({
          lot_number: '4',
          est_resale_low: 40,
          est_resale_high: 70,
          est_retail_price: retail,
        })
      );
      expect(html).toContain('data-testid="resale-summary"');
      expect(html).toContain('$55');
      expect(html).not.toContain('$0');
    }
  });

  it('shows the condition word and the bucket, falling back to the subcategory', () => {
    const plain = renderCard(lot({ lot_number: '5', condition: 'Like New' }));
    expect(plain).toContain('LIKE NEW');
    expect(plain).toContain('Hand Tools'); // no bucket → subcategory

    const bat = renderCard(
      lot({ lot_number: '6', is_bat: true, bat_buckets: ['Kitchen appliances'] })
    );
    expect(bat).toContain('Kitchen appliances');
  });

  it('renders cleanly with no condition at all', () => {
    const html = renderCard(lot({ lot_number: '7', condition: null }));
    expect(html).toContain('data-testid="lot-card"');
    expect(html).not.toContain('null');
  });
});

describe('LotCard personal-pick badge', () => {
  it('renders the badge only when personal_match is true', () => {
    const html = renderCard(
      lot({ lot_number: '1', personal_match: true, match_strength: 'strong' })
    );
    expect(html).toContain('data-testid="personal-badge"');
    // The badge is now a 6px dot on the thumb rather than a chip in the text
    // block — it costs zero layout, so its label is the accessible name.
    expect(html).toContain('aria-label="Personal pick"');
  });

  it('no badge for false, null, or absent personal_match', () => {
    for (const l of [
      lot({ lot_number: '2', personal_match: false }),
      lot({ lot_number: '3', personal_match: null }),
      lot({ lot_number: '4' }), // fields absent (older bundle)
    ]) {
      const html = renderCard(l);
      expect(html).not.toContain('data-testid="personal-badge"');
      expect(html).not.toContain('Personal pick');
    }
  });

  it('badge is independent of Bat/resale chips (a plain lot can be a pick)', () => {
    const html = renderCard(lot({ lot_number: '5', personal_match: true }));
    expect(html).toContain('data-testid="personal-badge"');
    expect(html).not.toContain('data-testid="resale-summary"');
  });
});

describe('LotCard watch state', () => {
  it('exposes the star as a pressed toggle with a lot-specific label', () => {
    const off = renderToStaticMarkup(
      <LotCard
        view={buildLotViews([lot({ lot_number: '1', title: 'Cordless drill' })])[0]}
        colW={196}
        textH={83}
        expanded={false}
        onToggleExpand={noop}
        watched={false}
        onToggleWatch={noop}
      />
    );
    expect(off).toContain('aria-pressed="false"');
    expect(off).toContain('Add to list: Cordless drill');

    const on = renderToStaticMarkup(
      <LotCard
        view={buildLotViews([lot({ lot_number: '1', title: 'Cordless drill' })])[0]}
        colW={196}
        textH={83}
        expanded={false}
        onToggleExpand={noop}
        watched
        onToggleWatch={noop}
      />
    );
    expect(on).toContain('aria-pressed="true"');
    expect(on).toContain('Remove from list: Cordless drill');
  });
});

