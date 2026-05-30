import Fuse from 'fuse.js';
import type { Lot } from './types';

// Fuse match tolerance. 0 = exact, 1 = match anything. ~0.3 tolerates typos
// and minor misspellings without flooding results. Tune here.
export const SEARCH_THRESHOLD = 0.3;

/**
 * Normalize a string for diacritic-insensitive matching:
 * decompose accents (NFD), strip combining marks, lowercase.
 * So "Wüsthof" → "wusthof", matching a "wustof" query.
 */
export function normalize(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

interface SearchDoc {
  lot_number: string;
  title: string;
  description: string;
  categories: string;
  subcategory: string;
}

/**
 * Build the Fuse index once on data load. Indexed fields are pre-normalized
 * for diacritic-insensitive matching. Searches cover title, description,
 * lot_number, every level of category_path, and subcategory.
 */
export function buildSearchIndex(lots: Lot[]): Fuse<SearchDoc> {
  const docs: SearchDoc[] = lots.map((l) => ({
    lot_number: l.lot_number,
    title: normalize(l.title),
    description: normalize(l.description),
    categories: normalize(l.category_path.join(' ')),
    subcategory: normalize(l.subcategory),
  }));

  return new Fuse(docs, {
    keys: [
      { name: 'title', weight: 0.5 },
      { name: 'categories', weight: 0.2 },
      { name: 'subcategory', weight: 0.15 },
      { name: 'description', weight: 0.1 },
      { name: 'lot_number', weight: 0.05 },
    ],
    threshold: SEARCH_THRESHOLD,
    ignoreLocation: true, // match anywhere in long descriptions
    includeScore: false,
    minMatchCharLength: 2,
  });
}

/**
 * Run a fuzzy search and return the set of matching lot_numbers. Callers
 * intersect this with the structurally-filtered rows so search never bypasses
 * the active tab / category / day filters.
 *
 * Multi-word queries are AND-combined per token: each whitespace-separated
 * token is fuzzy-searched independently and the result sets intersected. This
 * makes "dewalt drll" match a "DEWALT … Drill" lot (token "dewalt" matches the
 * brand, "drll" fuzzy-matches "drill") even when other words sit between them —
 * which a single whole-string fuzzy pass would miss.
 */
export function fuzzyMatchLotNumbers(fuse: Fuse<SearchDoc>, query: string): Set<string> {
  const q = normalize(query.trim());
  if (!q) return new Set();

  const tokens = q.split(/\s+/).filter(Boolean);
  if (tokens.length === 1) {
    return new Set(fuse.search(tokens[0]).map((r) => r.item.lot_number));
  }

  let acc: Set<string> | null = null;
  for (const token of tokens) {
    const matches = new Set(fuse.search(token).map((r) => r.item.lot_number));
    if (acc === null) {
      acc = matches;
    } else {
      const prev: Set<string> = acc;
      acc = new Set([...prev].filter((ln) => matches.has(ln)));
    }
    if (acc.size === 0) break;
  }
  return acc ?? new Set<string>();
}
