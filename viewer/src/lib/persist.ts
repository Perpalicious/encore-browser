import type {
  Condition,
  ConfidenceFilter,
  DayFilter,
  Density,
  MobileCols,
  MobileView,
  OutlookFilter,
  SortKey,
  Tab,
  ViewMode,
} from './types';

/**
 * View-state persistence — docs/design/README.md § "Persistence".
 *
 * Two destinations with different jobs:
 *
 *  - The URL hash carries everything that describes WHAT YOU ARE LOOKING AT, so
 *    a filtered view is a link you can send to someone at the venue.
 *  - localStorage carries the same, plus the things that are yours alone and
 *    would be meaningless (or hostile) to share: your watch list and where you
 *    were scrolled to.
 *
 * On load the hash wins, so following a link overrides your last session
 * without destroying it.
 */

export const STORAGE_KEY = 'encore.lotbrowser.v1';
export const WATCHED_KEY = 'encore_watched';
export const SCROLL_KEY = 'encore.scroll.v1';
/** Long enough that a burst of typing or chip-clicking writes once. */
export const PERSIST_DEBOUNCE_MS = 350;

/** The shareable half of the state. */
export interface ViewState {
  tab: Tab;
  q: string;
  fuzzy: boolean;
  cat: string[];
  sort: SortKey;
  conds: Condition[];
  conf: ConfidenceFilter;
  out: OutlookFilter;
  picks: boolean;
  resales: boolean;
  day: DayFilter;
  view: ViewMode;
  mView: MobileView;
  cols: MobileCols;
  density: Density;
  bucket: string | null;
}

export const DEFAULT_VIEW_STATE: ViewState = {
  tab: 'all',
  q: '',
  fuzzy: false,
  cat: [],
  sort: 'lot',
  conds: [],
  conf: 'all',
  out: 'all',
  picks: false,
  resales: false,
  day: 'Both',
  view: 'grid',
  mView: 'rows',
  cols: 3,
  density: 'standard',
  bucket: null,
};

const TABS: Tab[] = ['all', 'bat', 'watched'];
const SORTS: SortKey[] = ['lot', 'resale-desc', 'resale-asc', 'retail-desc'];
const CONFS: ConfidenceFilter[] = ['all', 'high', 'medium-plus'];
const OUTS: OutlookFilter[] = ['all', 'poor', 'fair', 'good'];
const DAYS: DayFilter[] = ['Sunday', 'Monday', 'Both'];
const VIEWS: ViewMode[] = ['grid', 'list'];
const MVIEWS: MobileView[] = ['rows', 'cards'];
const DENSITIES: Density[] = ['standard', 'compact'];
const CONDS: Condition[] = ['New', 'Like New', 'Good', 'Fair', 'Heavily Used'];

function oneOf<T>(value: unknown, allowed: T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/**
 * Coerce anything into a valid ViewState.
 *
 * Everything here arrives from a URL someone may have edited by hand or from a
 * localStorage blob written by an older build, so nothing is trusted: an
 * unrecognised value falls back to its default rather than propagating into the
 * filter pipeline as `undefined`.
 */
export function parseViewState(raw: unknown): ViewState {
  if (typeof raw !== 'object' || raw === null) return { ...DEFAULT_VIEW_STATE };
  const r = raw as Record<string, unknown>;
  const cols = Number(r.cols);
  return {
    tab: oneOf(r.tab, TABS, DEFAULT_VIEW_STATE.tab),
    q: typeof r.q === 'string' ? r.q : '',
    fuzzy: r.fuzzy === true,
    cat: Array.isArray(r.cat) ? r.cat.filter((c): c is string => typeof c === 'string') : [],
    sort: oneOf(r.sort, SORTS, DEFAULT_VIEW_STATE.sort),
    conds: Array.isArray(r.conds) ? CONDS.filter((c) => (r.conds as unknown[]).includes(c)) : [],
    conf: oneOf(r.conf, CONFS, DEFAULT_VIEW_STATE.conf),
    out: oneOf(r.out, OUTS, DEFAULT_VIEW_STATE.out),
    picks: r.picks === true,
    resales: r.resales === true,
    day: oneOf(r.day, DAYS, DEFAULT_VIEW_STATE.day),
    view: oneOf(r.view, VIEWS, DEFAULT_VIEW_STATE.view),
    mView: oneOf(r.mView, MVIEWS, DEFAULT_VIEW_STATE.mView),
    cols: (cols === 2 || cols === 3 || cols === 4 ? cols : DEFAULT_VIEW_STATE.cols) as MobileCols,
    density: oneOf(r.density, DENSITIES, DEFAULT_VIEW_STATE.density),
    bucket: typeof r.bucket === 'string' ? r.bucket : null,
  };
}

/** Drop defaults, so a pristine view produces an empty hash rather than noise. */
function pruned(state: ViewState): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(state)) {
    const def = DEFAULT_VIEW_STATE[k as keyof ViewState];
    if (JSON.stringify(v) !== JSON.stringify(def)) out[k] = v;
  }
  return out;
}

export function encodeHash(state: ViewState): string {
  const p = pruned(state);
  if (Object.keys(p).length === 0) return '';
  return `#s=${encodeURIComponent(JSON.stringify(p))}`;
}

export function decodeHash(hash: string): ViewState | null {
  const m = /[#&]s=([^&]+)/.exec(hash);
  if (!m) return null;
  try {
    return parseViewState(JSON.parse(decodeURIComponent(m[1])));
  } catch {
    return null;
  }
}

/** The hash wins over localStorage, so a shared link lands on its own view. */
export function loadViewState(): ViewState {
  const fromHash = typeof location !== 'undefined' ? decodeHash(location.hash) : null;
  if (fromHash) return fromHash;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return parseViewState(JSON.parse(raw));
  } catch {
    // ignore
  }
  return { ...DEFAULT_VIEW_STATE };
}

export function saveViewState(state: ViewState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pruned(state)));
  } catch {
    // ignore
  }
  try {
    const hash = encodeHash(state);
    // replaceState, not location.hash — filtering should not fill the back
    // button with one entry per keystroke.
    history.replaceState(null, '', `${location.pathname}${location.search}${hash}`);
  } catch {
    // ignore
  }
}

export function loadScrollTop(): number {
  try {
    const raw = localStorage.getItem(SCROLL_KEY);
    const n = raw === null ? 0 : Number(raw);
    return Number.isFinite(n) && n >= 0 ? n : 0;
  } catch {
    return 0;
  }
}

export function saveScrollTop(value: number): void {
  try {
    localStorage.setItem(SCROLL_KEY, String(Math.round(value)));
  } catch {
    // ignore
  }
}
