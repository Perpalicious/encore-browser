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

  it('shows each term count and dims a term with none this week', () => {
    const counts = new Map([['clamps', 12], ['tie downs', 0]]);
    const html = renderToStaticMarkup(
      <LegendStrip groups={GROUPS} counts={counts} onPick={() => {}} onClose={() => {}} />
    );
    expect(html.match(/data-testid="legend-count"/g)?.length).toBe(2);
    expect(html).toMatch(/clamps<span[^>]*data-testid="legend-count"[^>]*>12</);
    expect(html.match(/data-empty="true"/g)?.length).toBe(1);
    expect(html).toContain('opacity:0.45');
    expect(html).toContain('No lots this week');
  });

  it('renders no counts when none are given', () => {
    const html = renderToStaticMarkup(
      <LegendStrip groups={GROUPS} onPick={() => {}} onClose={() => {}} />
    );
    expect(html).not.toContain('legend-count');
    expect(html).not.toContain('data-empty');
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
