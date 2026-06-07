import Fuse from 'fuse.js';
import type { Lot } from './types';

// Fuse match tolerance, used ONLY when fuzzy mode is on. 0 = exact,
// 1 = matches anything. Tightened from 0.3 → 0.2 so fuzzy stays close to the
// query and stops flooding results. Single source of truth — adjust here.
export const SEARCH_THRESHOLD = 0.2;

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

// Fields the FUZZY pass tolerates typos on. Deliberately narrow: the full
// description and the joined category_path are NOT fuzzy-matched (matching
// fuzzily across long free text was the main source of loose results). Those
// two fields are still covered by exact substring in BOTH modes.
interface FuseDoc {
  lot_number: string;
  title: string;
  subcategory: string;
}

interface ExactDoc {
  lot_number: string;
  // Every searchable field, normalized and space-joined — used by exact mode.
  all: string;
  // description + category_path only — fuzzy mode substring-matches these so a
  // query found only in the description/categories still hits in fuzzy mode.
  descCat: string;
}

export interface SearchIndex {
  fuse: Fuse<FuseDoc>;
  docs: ExactDoc[];
}

/**
 * Build the search index once on data load (one pass over all lots). Holds both
 * a Fuse index over the narrow fuzzy-field set and a normalized doc per lot for
 * exact substring matching. All text is pre-normalized for diacritic-
 * insensitive, case-insensitive matching.
 */
export function buildSearchIndex(lots: Lot[]): SearchIndex {
  const fuseDocs: FuseDoc[] = [];
  const docs: ExactDoc[] = [];

  for (const l of lots) {
    const title = normalize(l.title);
    const subcategory = normalize(l.subcategory);
    const lotNo = normalize(l.lot_number);
    const description = normalize(l.description);
    const categories = normalize(l.category_path.join(' '));

    fuseDocs.push({ lot_number: l.lot_number, title, subcategory });
    docs.push({
      lot_number: l.lot_number,
      all: [title, subcategory, lotNo, description, categories].join('  '),
      descCat: [description, categories].join('  '),
    });
  }

  const fuse = new Fuse(fuseDocs, {
    keys: [
      { name: 'title', weight: 0.7 },
      { name: 'subcategory', weight: 0.2 },
      { name: 'lot_number', weight: 0.1 },
    ],
    threshold: SEARCH_THRESHOLD,
    ignoreLocation: true, // match anywhere, not just near the start
    includeScore: false,
    minMatchCharLength: 2,
  });

  return { fuse, docs };
}

/** Split a query into normalized, whitespace-separated tokens. */
function tokenize(query: string): string[] {
  return normalize(query.trim()).split(/\s+/).filter(Boolean);
}

/**
 * Fuse search per token, AND-combined: each token is searched independently and
 * the result sets intersected. So "dewalt drll" matches a "DEWALT … Drill" lot
 * even with words between them — which a single whole-string pass would miss.
 */
function fuseTokenAnd(fuse: Fuse<FuseDoc>, tokens: string[]): Set<string> {
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

/**
 * EXACT (default) matching: strict substring, diacritic-normalized and
 * case-insensitive, across ALL fields (title, subcategory, lot_number,
 * description, category_path). Multi-word queries AND-match — every token must
 * appear somewhere in the lot's text. "dewalt" returns only lots that actually
 * contain "dewalt", not fuzzy-adjacent noise.
 */
export function exactMatchLotNumbers(index: SearchIndex, query: string): Set<string> {
  const tokens = tokenize(query);
  if (!tokens.length) return new Set();
  const out = new Set<string>();
  for (const d of index.docs) {
    if (tokens.every((t) => d.all.includes(t))) out.add(d.lot_number);
  }
  return out;
}

/**
 * FUZZY (opt-in) matching: typo-tolerant Fuse over the narrow field set
 * (title + subcategory + lot_number), UNION-ed with exact substring over
 * description + category_path. The union keeps fuzzy mode a strict superset of
 * what those two long fields would match, without fuzzing across them.
 */
export function fuzzyMatchLotNumbers(index: SearchIndex, query: string): Set<string> {
  const tokens = tokenize(query);
  if (!tokens.length) return new Set();

  const out = fuseTokenAnd(index.fuse, tokens);
  for (const d of index.docs) {
    if (!out.has(d.lot_number) && tokens.every((t) => d.descCat.includes(t))) {
      out.add(d.lot_number);
    }
  }
  return out;
}

/**
 * Dispatch to exact (default) or fuzzy (opt-in) matching. Callers intersect the
 * result with the structurally-filtered rows so search always narrows within
 * the active tab / category / day view, never bypasses it.
 */
export function searchLotNumbers(
  index: SearchIndex,
  query: string,
  fuzzy: boolean
): Set<string> {
  return fuzzy ? fuzzyMatchLotNumbers(index, query) : exactMatchLotNumbers(index, query);
}
