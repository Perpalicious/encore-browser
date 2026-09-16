import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { LegendButton, LegendStrip } from './RecallLegend';
import { LEGEND_GROUPS } from '../lib/legend';

const GROUPS = [
  { name: 'Tools & garage', terms: ['clamps', 'tie downs'] },
  { name: 'Outdoor', terms: ['garden hose'] },
];

describe('RecallLegend', () => {
  it('renders every group name and one chip per term', () => {
    const html = renderToStaticMarkup(
      <LegendStrip groups={GROUPS} onPick={() => {}} onClose={() => {}} />
    );
    expect(html).toContain('data-testid="legend-strip"');
    expect(html).toContain('Tools &amp; garage');
    expect(html).toContain('Outdoor');
    expect(html.match(/data-testid="legend-term"/g)?.length).toBe(3);
    expect(html).toContain('data-testid="legend-close"');
  });

  it('renders nothing without groups', () => {
    expect(renderToStaticMarkup(<LegendStrip groups={[]} onPick={() => {}} onClose={() => {}} />)).toBe('');
  });

  it('the button reports its state', () => {
    expect(renderToStaticMarkup(<LegendButton open={false} onToggle={() => {}} />)).toContain('aria-expanded="false"');
    expect(renderToStaticMarkup(<LegendButton open onToggle={() => {}} />)).toContain('aria-expanded="true"');
  });

  it('the committed legend JSON is well-formed', () => {
    expect(LEGEND_GROUPS.length).toBeGreaterThan(0);
    const all = LEGEND_GROUPS.flatMap((g) => g.terms.map((t) => t.toLowerCase()));
    expect(new Set(all).size).toBe(all.length);
  });
});
