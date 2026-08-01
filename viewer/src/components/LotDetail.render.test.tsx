import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Lot } from '../lib/types';
import { lotView } from '../test/lotFixture';
import { LotDetail } from './LotDetail';

const noop = () => {};

function renderDetail(
  partial: Partial<Lot> & { lot_number: string },
  overrides: { index?: number; total?: number; sheet?: boolean; watched?: boolean } = {}
): string {
  return renderToStaticMarkup(
    <LotDetail
      view={lotView(partial)}
      index={overrides.index ?? 0}
      total={overrides.total ?? 10}
      sheet={overrides.sheet ?? false}
      watched={overrides.watched ?? false}
      onClose={noop}
      onStep={noop}
      onToggleWatch={noop}
    />
  );
}

describe('LotDetail resale block', () => {
  it('renders the range, confidence, outlook and note when valued', () => {
    const html = renderDetail({
      lot_number: 'S-1',
      est_resale_low: 40,
      est_resale_high: 70,
      est_retail_price: 120,
      resale_confidence: 'medium',
      resale_outlook: 'good',
      resale_reasoning: 'Comparable units resell steadily.',
    });
    expect(html).toContain('data-testid="resale-detail"');
    expect(html).toContain('$40–$70');
    expect(html).toContain('$120');
    expect(html).toContain('MEDIUM CONFIDENCE');
    expect(html).toContain('GOOD OUTLOOK');
    expect(html).toContain('Comparable units resell steadily.');
  });

  it('omits the whole block when there is neither a resale nor a retail figure', () => {
    expect(renderDetail({ lot_number: 'S-2' })).not.toContain('data-testid="resale-detail"');
  });

  it('shows retail alone when the lot was never valued', () => {
    const html = renderDetail({ lot_number: 'S-3', est_retail_price: 120 });
    expect(html).toContain('data-testid="resale-detail"');
    expect(html).toContain('RETAIL');
    expect(html).not.toContain('RESALE');
  });

  it('never invents a fourth outlook step', () => {
    // Our resale pass emits poor/fair/good only; the handoff assumes a
    // 'Strong' above 'Good' that must not appear anywhere.
    for (const out of ['poor', 'fair', 'good'] as const) {
      const html = renderDetail({
        lot_number: 'S-1',
        est_resale_low: 10,
        est_resale_high: 20,
        resale_outlook: out,
      });
      expect(html).toContain(`${out.toUpperCase()} OUTLOOK`);
      expect(html).not.toContain('STRONG OUTLOOK');
    }
  });

  it('flags a top-decile spread only when the lot carries the tick', () => {
    // A single-lot set makes that lot its own 90th percentile.
    const ticked = renderDetail({
      lot_number: 'S-1',
      est_resale_low: 40,
      est_resale_high: 70,
      est_retail_price: 120,
    });
    expect(ticked).toContain('data-testid="top-decile-badge"');

    const noRatio = renderDetail({
      lot_number: 'S-2',
      est_resale_low: 40,
      est_resale_high: 70,
      est_retail_price: 0,
    });
    expect(noRatio).not.toContain('data-testid="top-decile-badge"');
  });
});

describe('LotDetail personal block', () => {
  it('renders strength, reasoning and tags when present', () => {
    const html = renderDetail({
      lot_number: 'S-1',
      personal_match: true,
      match_strength: 'strong',
      personal_tags: ['woodworking', 'power tools'],
      personal_reasoning: 'Matches the workshop tool interest.',
    });
    expect(html).toContain('data-testid="personal-detail"');
    expect(html).toContain('PERSONAL PICK · STRONG MATCH');
    expect(html).toContain('data-testid="personal-reasoning"');
    expect(html).toContain('Matches the workshop tool interest.');
    expect(html).toContain('data-testid="personal-tags"');
    expect(html).toContain('woodworking');
    expect(html).toContain('power tools');
  });

  it('omits tags/reasoning rows cleanly when only personal_match is set', () => {
    const html = renderDetail({ lot_number: 'S-2', personal_match: true });
    expect(html).toContain('data-testid="personal-detail"');
    expect(html).toContain('PERSONAL PICK');
    expect(html).not.toContain('data-testid="personal-tags"');
    expect(html).not.toContain('data-testid="personal-reasoning"');
  });

  it("does not print the 'none' strength sentinel", () => {
    const html = renderDetail({
      lot_number: 'S-3',
      personal_match: true,
      match_strength: 'none',
    });
    expect(html).toContain('PERSONAL PICK');
    expect(html).not.toContain('NONE MATCH');
  });

  it('omits the personal block entirely when not a pick', () => {
    for (const l of [
      { lot_number: 'S-4', personal_match: false },
      { lot_number: 'S-5' },
    ]) {
      expect(renderDetail(l)).not.toContain('data-testid="personal-detail"');
    }
  });
});

describe('LotDetail stepper and chrome', () => {
  it('disables the stepper at each end of the result set', () => {
    const first = renderDetail({ lot_number: 'S-1' }, { index: 0, total: 5 });
    expect(first).toMatch(/data-testid="detail-prev"[^>]*disabled/);
    expect(first).not.toMatch(/data-testid="detail-next"[^>]*disabled/);

    const last = renderDetail({ lot_number: 'S-1' }, { index: 4, total: 5 });
    expect(last).toMatch(/data-testid="detail-next"[^>]*disabled/);
    expect(last).not.toMatch(/data-testid="detail-prev"[^>]*disabled/);
  });

  it('links out to the Encore lot page', () => {
    const html = renderDetail({ lot_number: 'S-1' });
    expect(html).toContain('href="https://encoreauctions.hibid.com/lot/1/x"');
    expect(html).toContain('View on Encore');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it('names the day and lot in the meta line', () => {
    expect(renderDetail({ lot_number: 'S-1' })).toContain('SUNDAY · LOT S-1');
    expect(renderDetail({ lot_number: 'M-9', day: '' })).toContain('MONDAY · LOT M-9');
  });

  it('renders as a drawer on a pointer device and a sheet on a touch device', () => {
    expect(renderDetail({ lot_number: 'S-1' }, { sheet: false })).toContain('width:430px');
    const sheet = renderDetail({ lot_number: 'S-1' }, { sheet: true });
    expect(sheet).toContain('88dvh');
    expect(sheet).toContain('border-radius:18px 18px 0 0');
  });
});
