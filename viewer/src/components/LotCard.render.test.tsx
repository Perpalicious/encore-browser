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
    // HiBid's grading verbatim; the card uppercases it for display.
    const plain = renderCard(lot({ lot_number: '5', condition: 'Brand New - Open Box' }));
    expect(plain).toContain('BRAND NEW - OPEN BOX');
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


/** Render with the extra props the auction-day features need. */
function renderCardWith(
  l: Lot,
  extra: { now?: number; singleDay?: boolean } = {}
): string {
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
      {...extra}
    />
  );
}

describe('LotCard day chip', () => {
  it('marks a Sunday lot S and a Monday lot M', () => {
    expect(renderCardWith(lot({ lot_number: 'S-1204' }))).toContain('day-chip-S');
    expect(renderCardWith(lot({ lot_number: 'M-1204' }))).toContain('day-chip-M');
  });

  it('uses a different pastel per day, so the two read apart at a glance', () => {
    expect(renderCardWith(lot({ lot_number: 'S-1' }))).toContain('--lavbg');
    expect(renderCardWith(lot({ lot_number: 'M-1' }))).toContain('--blushbg');
  });

  it('is dropped when a single day is already filtered', () => {
    const html = renderCardWith(lot({ lot_number: 'S-1204' }), { singleDay: true });
    expect(html).not.toContain('day-chip');
  });

  it('is labelled, since a bare letter is not self-explanatory', () => {
    expect(renderCardWith(lot({ lot_number: 'S-1' }))).toContain('Sunday auction');
  });
});

describe('LotCard closing time', () => {
  const soon = new Date(2026, 7, 9, 13, 4).toISOString();
  const now = new Date(2026, 7, 9, 12, 0).getTime();

  it('shows the time beside the condition', () => {
    const html = renderCardWith(lot({ lot_number: 'S-1', close_at: soon }), { now });
    expect(html).toContain('close-time');
    expect(html).toContain('1:04p');
  });

  it('says ENDED once the time has passed', () => {
    const past = new Date(2026, 7, 9, 14, 0).getTime();
    const html = renderCardWith(lot({ lot_number: 'S-1', close_at: soon }), { now: past });
    expect(html).toContain('ENDED');
    expect(html).not.toContain('1:04p');
    // Dimmed rather than removed, so you can see where the auction has got to.
    expect(html).toContain('opacity:0.55');
  });

  it('renders nothing time-related on a bundle without close_at', () => {
    // This is the live site's state until the next pipeline run.
    const html = renderCardWith(lot({ lot_number: 'S-1' }), { now });
    expect(html).not.toContain('close-time');
    expect(html).not.toContain('ENDED');
    expect(html).not.toContain('opacity:0.55');
  });

  it('renders no time when the app passes no clock', () => {
    const html = renderCardWith(lot({ lot_number: 'S-1', close_at: soon }));
    // The time itself still shows; only the ENDED comparison needs a clock.
    expect(html).toContain('1:04p');
    expect(html).not.toContain('ENDED');
  });
});
