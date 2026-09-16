import raw from '../data/recall_legend.json';

/**
 * The recall legend — the search terms we tend to forget to run.
 *
 * Generated from `recall_legend.yaml` by `tools/recall_legend.py build`; the
 * YAML is the thing to edit. A term is only ever a string dropped into the
 * search box: nothing here touches filtering.
 */
export interface LegendGroup {
  name: string;
  terms: string[];
}

function clean(input: unknown): LegendGroup[] {
  const groups = (input as { groups?: unknown })?.groups;
  if (!Array.isArray(groups)) return [];
  const out: LegendGroup[] = [];
  for (const g of groups) {
    const name = typeof g?.name === 'string' ? g.name.trim() : '';
    const terms = Array.isArray(g?.terms)
      ? g.terms.filter((t: unknown): t is string => typeof t === 'string' && t.trim() !== '')
      : [];
    if (name && terms.length > 0) out.push({ name, terms });
  }
  return out;
}

export const LEGEND_GROUPS: LegendGroup[] = clean(raw);
