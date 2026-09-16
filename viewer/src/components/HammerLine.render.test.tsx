import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { HammerWeek, Lot } from '../lib/types';
import type { HammerHistory } from '../lib/hammer';
import { buildLotViews } from '../lib/lotView';
import { lot, lotView } from '../test/lotFixture';
import { LotCard } from './LotCard';
import { LotRow } from './LotRow';
import { LotDetail } from './LotDetail';

/**
 * The hammer-price line: what this same product actually sold for in past
 * auctions. One compact line on the card and the row, the full per-week table
 * in the detail overlay. Absent entirely on a lot with no history, which is
 * roughly two lots in three and every lot until Bat runs the pull.
 */

const noop = () => {};

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

/** A history that is the lot's own, or null for none — the pre-fallback shape. */
function own(weeks: HammerWeek[] | null): HammerHistory | null {
  return weeks && weeks.length > 0 ? { own: weeks, others: [] } : null;
}

/** A history with no exact match, only another grade's. */
function borrowed(condition: string, weeks: HammerWeek[]): HammerHistory {
  return { own: null, others: [{ condition, weeks }] };
}

function renderCard(l: Lot, hammer: HammerHistory | null, colW = 260): string {
  const [view] = buildLotViews([l]);
  return renderToStaticMarkup(
    <LotCard
      view={view}
      colW={colW}
      textH={83}
      expanded={false}
      onToggleExpand={noop}
      watched={false}
      onToggleWatch={noop}
      hammer={hammer}
    />
  );
}

function renderRow(l: Lot, hammer: HammerHistory | null, mobile = false): string {
  const [view] = buildLotViews([l]);
  return renderToStaticMarkup(
    <LotRow
      view={view}
      mobile={mobile}
      coarse={false}
      touch={false}
      height={67}
      watched={false}
      cursor={false}
      onOpen={noop}
      onToggleWatch={noop}
      hammer={hammer}
    />
  );
}

function renderDetail(l: Lot, hammer: HammerHistory | null): string {
  return renderToStaticMarkup(
    <LotDetail
      view={lotView(l)}
      index={0}
      total={10}
      sheet={false}
      watched={false}
      onClose={noop}
      onStep={noop}
      onToggleWatch={noop}
      hammer={hammer}
    />
  );
}

describe('LotCard hammer line', () => {
  it('shows the latest week only', () => {
    const html = renderCard(lot({ lot_number: '1' }), own([
      week(),
      week({ close_date: '2026-09-06', sold: 2, median: 30 }),
    ]));
    expect(html).toContain('data-testid="hammer-line"');
    expect(html).toContain('Sold 6× · med $14 · $9–$22 · 3 unsold');
    expect(html).not.toContain('$30'); // the older week belongs in the detail
  });

  it('sheds the range at standard density, and the unsold count when compact', () => {
    const weeks = own([week()]);
    expect(renderCard(lot({ lot_number: '1' }), weeks, 196)).toContain(
      'Sold 6× · med $14 · 3 unsold'
    );
    expect(renderCard(lot({ lot_number: '1' }), weeks, 150)).toContain('Sold 6× · med $14');
  });

  it('counts unsold lots rather than pricing them at zero', () => {
    const html = renderCard(lot({ lot_number: '1' }), own([
      week({ sold: 0, unsold: 12, median: null, low: null, high: null }),
    ]));
    expect(html).toContain('Listed 12× · none sold');
    expect(html).not.toContain('$0');
  });

  it('renders nothing at all when the lot has no history', () => {
    for (const h of [null, own([])]) {
      const html = renderCard(lot({ lot_number: '1' }), h);
      expect(html).not.toContain('data-testid="hammer-line"');
    }
  });

  it('stays clear of the resale figure — smaller, and not the --text weight', () => {
    // docs/design/README.md § "The signal system": the hammer line is history,
    // not a second valuation, so it must not compete with resale's typography.
    const html = renderCard(
      lot({ lot_number: '1', est_resale_low: 40, est_resale_high: 70 }),
      own([week()])
    );
    expect(html).toContain('data-testid="resale-summary"');
    expect(html).toContain('data-testid="hammer-line"');
    expect(html).toContain('font-size:8.5px');
    expect(html).toContain('color:var(--dim3)');
  });
});

describe('LotCard borrowed line (another grade of the same title)', () => {
  it('names the grade it came from and never reads as this lot\'s own history', () => {
    const html = renderCard(lot({ lot_number: '1', condition: 'Good' }), borrowed('EXCELLENT', [week()]));
    expect(html).toContain('data-testid="hammer-line"');
    expect(html).toContain('data-borrowed="true"');
    expect(html).toContain('Excellent: Sold 6× · med $14 · 3 unsold');
    expect(html).toContain('font-style:italic');
    expect(html).toContain('No sales of this exact grade yet');
  });

  it('shortens HiBid\'s long grade names so the label fits the card', () => {
    const html = renderCard(lot({ lot_number: '1' }), borrowed('BRAND NEW - OPEN BOX', [week()]), 150);
    expect(html).toContain('Open box: Sold 6× · med $14');
    expect(html).not.toContain('BRAND NEW');
  });

  it('prefers the lot\'s own history over any other grade\'s', () => {
    const html = renderCard(lot({ lot_number: '1' }), {
      own: [week({ median: 3 })],
      others: [{ condition: 'BRAND NEW - OPEN BOX', weeks: [week({ median: 40 })] }],
    });
    expect(html).toContain('med $3');
    expect(html).not.toContain('$40');
    expect(html).not.toContain('data-borrowed');
  });
});

describe('LotRow hammer line', () => {
  it('carries the whole line on the wide desktop row', () => {
    const html = renderRow(lot({ lot_number: '1' }), own([week()]));
    expect(html).toContain('data-testid="hammer-line"');
    expect(html).toContain('Sold 6× · med $14 · $9–$22 · 3 unsold');
  });

  it('shortens to the median on the 78px mobile row', () => {
    const html = renderRow(lot({ lot_number: '1' }), own([week()]), true);
    expect(html).toContain('Sold 6× · med $14');
    expect(html).not.toContain('$9–$22');
  });

  it('renders nothing when the lot has no history', () => {
    expect(renderRow(lot({ lot_number: '1' }), null)).not.toContain(
      'data-testid="hammer-line"'
    );
    expect(renderRow(lot({ lot_number: '1' }), null, true)).not.toContain(
      'data-testid="hammer-line"'
    );
  });
});

describe('LotDetail hammer table', () => {
  it('lists every recorded week, newest first', () => {
    const html = renderDetail(lot({ lot_number: 'S-1' }), own([
      week(),
      week({ close_date: '2026-09-06', sold: 2, unsold: 0, median: 30, low: 28, high: 32 }),
    ]));
    expect(html).toContain('data-testid="hammer-detail"');
    expect(html).toContain('SOLD FOR, PAST WEEKS');
    expect(html.indexOf('Sep 13')).toBeLessThan(html.indexOf('Sep 6'));
    expect(html).toContain('$14');
    expect(html).toContain('$28–$32');
  });

  it('dashes the figures of a week that sold nothing', () => {
    const html = renderDetail(lot({ lot_number: 'S-1' }), own([
      week({ sold: 0, unsold: 12, median: null, low: null, high: null }),
    ]));
    expect(html).toContain('data-testid="hammer-detail"');
    expect(html).not.toContain('$0');
    expect(html).toContain('—');
  });

  it('omits the block entirely when there is no history', () => {
    for (const h of [null, undefined, own([])]) {
      expect(renderDetail(lot({ lot_number: 'S-1' }), h ?? null)).not.toContain(
        'data-testid="hammer-detail"'
      );
    }
  });

  it('leads with the lot\'s own grade, then lists the other grades under their names', () => {
    const html = renderDetail(lot({ lot_number: 'S-1', condition: 'Good' }), {
      own: [week({ median: 1 })],
      others: [
        { condition: 'EXCELLENT', weeks: [week({ median: 3 })] },
        { condition: 'BRAND NEW - OPEN BOX', weeks: [week({ median: 4 })] },
      ],
    });
    expect(html).toContain('data-testid="hammer-grade-own"');
    expect(html).toContain('Good · this lot');
    expect(html.indexOf('Good · this lot')).toBeLessThan(html.indexOf('Excellent'));
    expect(html.indexOf('Excellent')).toBeLessThan(html.indexOf('Open box'));
    expect(html.match(/data-testid="hammer-grade-other"/g)).toHaveLength(2);
  });

  it('still shows the lot\'s own grade as empty when only other grades have history', () => {
    const html = renderDetail(
      lot({ lot_number: 'S-1', condition: 'For Parts Only' }),
      borrowed('EXCELLENT', [week()])
    );
    expect(html).toContain('data-testid="hammer-detail"');
    expect(html).toContain('Parts only · this lot');
    expect(html).toContain('No sales of this grade yet');
    expect(html.indexOf('No sales of this grade yet')).toBeLessThan(html.indexOf('$14'));
  });

  it('sits alongside the resale block rather than replacing it', () => {
    const html = renderDetail(
      lot({ lot_number: 'S-1', est_resale_low: 40, est_resale_high: 70 }),
      own([week()])
    );
    expect(html).toContain('data-testid="resale-detail"');
    expect(html).toContain('data-testid="hammer-detail"');
    expect(html.indexOf('data-testid="resale-detail"')).toBeLessThan(
      html.indexOf('data-testid="hammer-detail"')
    );
  });
});
