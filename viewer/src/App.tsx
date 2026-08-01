import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import type {
  Tab,
  DayFilter,
  Density,
  Bundle,
  ConfidenceFilter,
  OutlookFilter,
  SortKey,
  Condition,
  ViewMode,
  MobileView,
  MobileCols,
} from './lib/types';
import { CONDITION_ORDER } from './lib/types';
import { filterLots } from './lib/filter';
import { sortLots } from './lib/sort';
import { buildCategoryTree } from './lib/categoryTree';
import { buildSearchIndex, searchLotNumbers } from './lib/search';
import { buildBatNav } from './lib/batNav';
import { buildLotViews, indexViews } from './lib/lotView';
import {
  loadViewState,
  saveViewState,
  loadScrollTop,
  saveScrollTop,
  PERSIST_DEBOUNCE_MS,
  HIDDEN_KEY,
  type ViewState,
} from './lib/persist';
import { useTheme } from './hooks/useTheme';
import { usePersistedSet } from './hooks/usePersistedSet';
import { useDebouncedValue } from './hooks/useDebouncedValue';
import { useMobileLayout, useCoarsePointer } from './hooks/useMediaQuery';
import { Header, type ActiveChip } from './components/Header';
import { FiltersOverlay } from './components/FiltersOverlay';
import { CategoryPopover } from './components/CategoryPopover';
import { LotGrid, type LotGridHandle } from './components/LotGrid';
import { LotDetail } from './components/LotDetail';
import { BatEmptyState } from './components/BatEmptyState';
import { Toast, useToast } from './components/Toast';

/** Whatever was in the URL hash or localStorage when this tab opened. */
const initial: ViewState = loadViewState();
const initialScrollTop = loadScrollTop();

export function App() {
  const [dark, toggleTheme] = useTheme();
  const [watched, toggleWatch] = usePersistedSet('encore_watched');
  const [hidden, toggleHidden] = usePersistedSet(HIDDEN_KEY);
  // Layout follows width; overlay affordances and swipe follow input device, so
  // a tablet gets the desktop grid but sheets, big hit areas and swipe triage.
  const mobileLayout = useMobileLayout();
  const coarsePointer = useCoarsePointer();
  const [toastMessage, showToast] = useToast();

  /**
   * The 40MB bundle is loaded ASYNCHRONOUSLY rather than as a static import.
   * As a static import it was part of the entry chunk, so the browser parsed
   * every one of the 26,457 lots before React could mount — and the "loading"
   * state was a 900ms setTimeout pretending that had happened. Now the
   * skeletons cover the real wait, and they clear when the index is genuinely
   * built.
   */
  const [bundle, setBundle] = useState<Bundle | null>(null);
  useEffect(() => {
    let cancelled = false;
    import('./data/auction_bundle.json').then((m) => {
      if (!cancelled) setBundle(m.default as unknown as Bundle);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const loading = bundle === null;

  const [query, setQuery] = useState(initial.q);
  // Search is EXACT (substring) by default; this opts into typo-tolerant fuzzy
  // matching.
  const [fuzzy, setFuzzy] = useState(initial.fuzzy);
  const [dayFilter, setDayFilter] = useState<DayFilter>(initial.day);
  const [categoryPath, setCategoryPath] = useState<string[]>(initial.cat);
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>(initial.conf);
  const [outlookFilter, setOutlookFilter] = useState<OutlookFilter>(initial.out);
  const [potentialOnly, setPotentialOnly] = useState(initial.resales);
  const [personalOnly, setPersonalOnly] = useState(initial.picks);
  const [density, setDensity] = useState<Density>(initial.density);
  const [tab, setTab] = useState<Tab>(initial.tab);
  const [view, setView] = useState<ViewMode>(initial.view);
  const [mobileView, setMobileView] = useState<MobileView>(initial.mView);
  const [mobileCols, setMobileCols] = useState<MobileCols>(initial.cols);
  // Bat's List: group → bucket. Null bucket = nothing picked yet (we prompt
  // rather than flood the grid with thousands of lots).
  const [batGroup, setBatGroup] = useState<string | null>(null);
  const [batBucket, setBatBucket] = useState<string | null>(initial.bucket);
  const [sortKey, setSortKey] = useState<SortKey>(initial.sort);
  const [conditions, setConditions] = useState<Set<Condition>>(new Set(initial.conds));
  // At most one lot is selected at a time; it opens the detail overlay.
  const [expandedId, setExpandedId] = useState<string | null>(null);
  // Keyboard cursor: an index into the filtered array, -1 when unset.
  const [cursor, setCursor] = useState(-1);
  // The rail's two overlays. Both are modal.
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [catOpen, setCatOpen] = useState(false);

  const gridRef = useRef<LotGridHandle>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const scrollTopRef = useRef(initialScrollTop);

  const allLots = useMemo(() => bundle?.lots ?? [], [bundle]);

  // The presentation mapping runs ONCE over the whole bundle — `tick` is a
  // top-decile threshold and has to see every lot, not whatever a filter left
  // behind. Filtering and sorting still work on the raw lots; the grid looks
  // each one's view up by lot number.
  const viewByLot = useMemo(() => indexViews(buildLotViews(allLots)), [allLots]);

  // The HiBid category hierarchy, fuzzy search index, and Bat's List
  // group→bucket tree, all built once the bundle lands.
  const categoryTree = useMemo(() => buildCategoryTree(allLots), [allLots]);
  const searchIndex = useMemo(() => buildSearchIndex(allLots), [allLots]);
  const batNav = useMemo(
    () => (bundle ? buildBatNav(allLots, bundle.bucket_groups, bundle.groups) : []),
    [allLots, bundle]
  );

  // Condition values actually present in the data, in canonical order.
  const availableConditions = useMemo<Condition[]>(() => {
    const present = new Set<Condition>();
    for (const l of allLots) if (l.condition !== null) present.add(l.condition);
    return CONDITION_ORDER.filter((c) => present.has(c));
  }, [allLots]);

  // Debounce the query so the fuzzy pass over ~26k lots doesn't run per keystroke.
  const debouncedQuery = useDebouncedValue(query, 150);

  const activeFilterCount =
    (dayFilter !== 'Both' ? 1 : 0) +
    (categoryPath.length > 0 ? 1 : 0) +
    (confidenceFilter !== 'all' ? 1 : 0) +
    (outlookFilter !== 'all' ? 1 : 0) +
    (potentialOnly ? 1 : 0) +
    (personalOnly ? 1 : 0) +
    (conditions.size > 0 ? 1 : 0) +
    (density !== 'standard' ? 1 : 0);

  const filtered = useMemo(() => {
    const rows = filterLots(allLots, {
      tab,
      dayFilter,
      categoryPath,
      batBucket,
      watched,
      hidden,
      confidenceFilter,
      outlookFilter,
      potentialOnly,
      personalOnly,
      conditions,
    });
    // Search narrows WITHIN the structural filters — it never bypasses the
    // active tab / category / day. Intersect matches with `rows`.
    if (debouncedQuery.trim()) {
      const matches = searchLotNumbers(searchIndex, debouncedQuery, fuzzy);
      return sortLots(rows.filter((l) => matches.has(l.lot_number)), sortKey);
    }
    return sortLots(rows, sortKey);
  }, [allLots, tab, debouncedQuery, fuzzy, dayFilter, categoryPath, batBucket, watched, hidden, confidenceFilter, outlookFilter, potentialOnly, personalOnly, conditions, sortKey, searchIndex]);

  /** Persist the shareable state, debounced, to both the hash and localStorage. */
  useEffect(() => {
    const state: ViewState = {
      tab,
      q: query,
      fuzzy,
      cat: categoryPath,
      sort: sortKey,
      conds: [...conditions],
      conf: confidenceFilter,
      out: outlookFilter,
      picks: personalOnly,
      resales: potentialOnly,
      day: dayFilter,
      view,
      mView: mobileView,
      cols: mobileCols,
      density,
      bucket: batBucket,
    };
    const t = setTimeout(() => saveViewState(state), PERSIST_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [tab, query, fuzzy, categoryPath, sortKey, conditions, confidenceFilter, outlookFilter, personalOnly, potentialOnly, dayFilter, view, mobileView, mobileCols, density, batBucket]);

  /** Scroll position is yours alone — localStorage only, never the hash. */
  useEffect(() => {
    const id = setInterval(() => saveScrollTop(scrollTopRef.current), 1000);
    const onLeave = () => saveScrollTop(scrollTopRef.current);
    window.addEventListener('pagehide', onLeave);
    return () => {
      clearInterval(id);
      window.removeEventListener('pagehide', onLeave);
      onLeave();
    };
  }, []);

  const toggleExpand = useCallback((lotNumber: string) => {
    setExpandedId((prev) => (prev === lotNumber ? null : lotNumber));
  }, []);

  // The detail overlay steps through the CURRENT result set, so its position is
  // derived from `filtered` rather than tracked separately — that way a filter
  // change can never leave the stepper pointing at a lot that is no longer in
  // view. An expanded lot filtered out of the results just closes the overlay.
  const selectedIndex = useMemo(
    () => (expandedId === null ? -1 : filtered.findIndex((l) => l.lot_number === expandedId)),
    [filtered, expandedId]
  );
  const selectedView =
    selectedIndex >= 0 ? viewByLot.get(filtered[selectedIndex].lot_number) : undefined;

  const stepSelection = (delta: number) => {
    const next = selectedIndex + delta;
    if (next < 0 || next >= filtered.length) return;
    setExpandedId(filtered[next].lot_number);
    setCursor(next);
    gridRef.current?.revealIndex(next);
  };

  const toggleCondition = useCallback((c: Condition) => {
    setConditions((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setQuery('');
    setDayFilter('Both');
    setCategoryPath([]);
    setConfidenceFilter('all');
    setOutlookFilter('all');
    setPotentialOnly(false);
    setPersonalOnly(false);
    setConditions(new Set());
    // Tab, density, and sort order are intentionally preserved.
  }, []);

  const onToggleWatch = useCallback(
    (lotNumber: string) => {
      toggleWatch(lotNumber);
      showToast(watched.has(lotNumber) ? 'Removed from list' : 'Added to list');
    },
    [toggleWatch, watched, showToast]
  );

  const onHide = useCallback(
    (lotNumber: string) => {
      toggleHidden(lotNumber);
      showToast(hidden.has(lotNumber) ? 'Restored' : 'Hidden');
    },
    [toggleHidden, hidden, showToast]
  );

  // The rail's category button reads as the deepest thing you picked.
  const categoryLabel =
    categoryPath.length > 0 ? categoryPath[categoryPath.length - 1] : 'All categories';

  // The rail's sort button cycles rather than opening a menu; the explicit
  // four-way select lives in the filters overlay.
  const cycleSort = () => {
    const CYCLE: SortKey[] = ['lot', 'resale-desc', 'retail-desc'];
    const i = CYCLE.indexOf(sortKey);
    setSortKey(CYCLE[(i + 1) % CYCLE.length]);
  };

  /**
   * Every active filter surfaces as a removable chip on the rail. This is the
   * half of the redesign that makes hiding the controls safe: the state is
   * always visible even when the control that set it is not.
   */
  const chips = useMemo<ActiveChip[]>(() => {
    const out: ActiveChip[] = [];
    if (categoryPath.length > 0) {
      out.push({
        id: 'category',
        label: categoryPath[categoryPath.length - 1],
        onRemove: () => setCategoryPath([]),
      });
    }
    if (dayFilter !== 'Both') {
      out.push({ id: 'day', label: dayFilter, onRemove: () => setDayFilter('Both') });
    }
    for (const c of CONDITION_ORDER) {
      if (conditions.has(c)) {
        out.push({ id: `condition-${c}`, label: c, onRemove: () => toggleCondition(c) });
      }
    }
    if (confidenceFilter !== 'all') {
      out.push({
        id: 'confidence',
        label: confidenceFilter === 'high' ? 'High confidence' : 'Med+ confidence',
        onRemove: () => setConfidenceFilter('all'),
      });
    }
    if (outlookFilter !== 'all') {
      out.push({
        id: 'outlook',
        label: `${outlookFilter.charAt(0).toUpperCase()}${outlookFilter.slice(1)} outlook`,
        onRemove: () => setOutlookFilter('all'),
      });
    }
    if (personalOnly) {
      out.push({ id: 'picks', label: '♥ Personal picks', onRemove: () => setPersonalOnly(false) });
    }
    if (potentialOnly) {
      out.push({
        id: 'resales',
        label: '↗ Potential resales',
        onRemove: () => setPotentialOnly(false),
      });
    }
    if (query !== '') {
      out.push({ id: 'query', label: `“${query}”`, onRemove: () => setQuery('') });
    }
    if (tab === 'bat' && batBucket !== null) {
      // Once a bucket is picked the picker is replaced by its lots, so this
      // chip is the way back to it — the old dropdown could be re-opened in
      // place, and switching buckets must stay a one-click move.
      out.push({
        id: 'bucket',
        label: `✦ ${batBucket}`,
        onRemove: () => setBatBucket(null),
      });
    }
    if (hidden.size > 0) {
      out.push({
        id: 'hidden',
        label: `${hidden.size} hidden`,
        onRemove: () => {
          for (const id of [...hidden]) toggleHidden(id);
          showToast('Hidden lots restored');
        },
      });
    }
    return out;
  }, [categoryPath, dayFilter, conditions, confidenceFilter, outlookFilter, personalOnly, potentialOnly, query, hidden, tab, batBucket, toggleCondition, toggleHidden, showToast]);

  const closeDetail = useCallback(() => setExpandedId(null), []);

  const anyOverlayOpen = filtersOpen || catOpen || expandedId !== null;

  /**
   * Keyboard navigation — docs/design/README.md § "Keyboard".
   *
   * Lot order runs left-to-right, and the keys follow that: →/← step one lot
   * and wrap across rows, ↓/↑ move by a full row. Movement scrolls the
   * container by direct arithmetic rather than scrollIntoView, which would
   * fight the absolutely-positioned window.
   */
  useEffect(() => {
    if (mobileLayout) return; // keyboard nav is a desktop affordance
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);

      if (e.key === 'Escape') {
        if (typing) (target as HTMLInputElement).blur();
        else if (filtersOpen) setFiltersOpen(false);
        else if (catOpen) setCatOpen(false);
        else if (expandedId !== null) closeDetail();
        return;
      }
      if (typing) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === '/') {
        e.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (e.key === 'f') {
        e.preventDefault();
        setFiltersOpen((v) => !v);
        return;
      }
      if (anyOverlayOpen && (e.key === 'w' || e.key === ' ' || e.key === 'Enter')) {
        // Let the overlay own these while it is up, except for stepping.
        if (e.key !== 'w') return;
      }
      if (filtered.length === 0) return;

      const step = (delta: number) => {
        e.preventDefault();
        const from = cursor < 0 ? 0 : cursor;
        const next = Math.max(0, Math.min(filtered.length - 1, from + delta));
        setCursor(next);
        gridRef.current?.revealIndex(next);
        // While the overlay is open, moving the cursor advances the overlay too.
        if (expandedId !== null) setExpandedId(filtered[next].lot_number);
      };

      const cols = gridRef.current?.cols ?? 1;
      switch (e.key) {
        case 'ArrowRight':
        case 'l':
          return step(1);
        case 'ArrowLeft':
        case 'h':
          return step(-1);
        case 'ArrowDown':
        case 'j':
          return step(cols);
        case 'ArrowUp':
        case 'k':
          return step(-cols);
        case ' ':
        case 'Enter': {
          e.preventDefault();
          const i = cursor < 0 ? 0 : cursor;
          setCursor(i);
          toggleExpand(filtered[i].lot_number);
          return;
        }
        case 'w': {
          e.preventDefault();
          const i = cursor < 0 ? 0 : cursor;
          onToggleWatch(filtered[i].lot_number);
          return;
        }
        default:
          return;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileLayout, filtered, cursor, expandedId, filtersOpen, catOpen, anyOverlayOpen, closeDetail, toggleExpand, onToggleWatch]);

  const handleTabChange = (t: Tab) => {
    setTab(t);
    setCursor(-1);
  };

  // Bat's List prompts for a bucket; until one is picked we show the group →
  // bucket picker instead of the grid (no thousands-of-items flood).
  const showBatPrompt = tab === 'bat' && batBucket === null;
  const sheet = mobileLayout || coarsePointer;

  return (
    // The app owns its scrolling: a fixed-height flex column whose grid scrolls
    // internally. The virtualiser measures its scrollTop against that container,
    // and the header rail sits above it and never leaves the viewport.
    <div className="h-[100dvh] flex flex-col overflow-hidden bg-bg text-text">
      <Header
        mobile={mobileLayout}
        dark={dark}
        onToggleTheme={toggleTheme}
        query={query}
        onQueryChange={setQuery}
        fuzzy={fuzzy}
        onFuzzyToggle={() => setFuzzy((v) => !v)}
        searchRef={searchRef}
        tab={tab}
        onTabChange={handleTabChange}
        watchedCount={watched.size}
        filteredCount={filtered.length}
        totalCount={allLots.length}
        loading={loading}
        categoryLabel={categoryLabel}
        categoryActive={categoryPath.length > 0}
        onOpenCategory={() => setCatOpen(true)}
        sortKey={sortKey}
        onCycleSort={cycleSort}
        onOpenFilters={() => setFiltersOpen(true)}
        activeFilterCount={activeFilterCount}
        chips={chips}
        onClearAll={clearFilters}
        view={view}
        onViewChange={setView}
        coarse={coarsePointer}
      />

      <main className="flex-1 min-h-0 flex flex-col">
        {showBatPrompt ? (
          <BatEmptyState
            groups={batNav}
            group={batGroup}
            bucket={batBucket}
            onGroupChange={setBatGroup}
            onBucketChange={setBatBucket}
          />
        ) : (
          <LotGrid
            ref={gridRef}
            lots={filtered}
            viewByLot={viewByLot}
            loading={loading}
            density={density}
            tab={tab}
            view={view}
            mobile={mobileLayout}
            coarse={coarsePointer}
            mobileView={mobileView}
            mobileCols={mobileCols}
            onMobileViewChange={setMobileView}
            onMobileColsChange={setMobileCols}
            cursor={cursor}
            onCursorChange={setCursor}
            expandedId={expandedId}
            watched={watched}
            onToggleExpand={toggleExpand}
            onToggleWatch={onToggleWatch}
            onHide={onHide}
            onClearFilters={clearFilters}
            singleDay={dayFilter !== 'Both'}
            initialScrollTop={initialScrollTop}
            onScrollTopChange={(v) => {
              scrollTopRef.current = v;
            }}
          />
        )}
      </main>

      {/* A visually hidden live region announces the result count. */}
      <p className="sr" aria-live="polite">
        {loading ? 'Loading lots' : `${filtered.length} lots match`}
      </p>

      {catOpen && (
        <CategoryPopover
          tree={categoryTree}
          selected={categoryPath}
          onChange={setCategoryPath}
          onClose={() => setCatOpen(false)}
          sheet={sheet}
        />
      )}

      {filtersOpen && (
        <FiltersOverlay
          sheet={sheet}
          resultCount={filtered.length}
          availableConditions={availableConditions}
          conditions={conditions}
          onToggleCondition={toggleCondition}
          confidenceFilter={confidenceFilter}
          onConfidenceChange={setConfidenceFilter}
          outlookFilter={outlookFilter}
          onOutlookChange={setOutlookFilter}
          dayFilter={dayFilter}
          onDayChange={setDayFilter}
          sortKey={sortKey}
          onSortChange={setSortKey}
          density={density}
          onDensityChange={setDensity}
          personalOnly={personalOnly}
          onPersonalToggle={() => setPersonalOnly((v) => !v)}
          potentialOnly={potentialOnly}
          onPotentialToggle={() => setPotentialOnly((v) => !v)}
          onClearAll={clearFilters}
          onClose={() => setFiltersOpen(false)}
        />
      )}

      {/* Detail overlay — never expands inside the grid, so the grid keeps its
          scroll position and you can step through candidates. */}
      {selectedView && (
        <LotDetail
          view={selectedView}
          index={selectedIndex}
          total={filtered.length}
          sheet={sheet}
          watched={watched.has(selectedView.lot)}
          onClose={closeDetail}
          onStep={stepSelection}
          onToggleWatch={() => onToggleWatch(selectedView.lot)}
        />
      )}

      {toastMessage && <Toast message={toastMessage} />}
    </div>
  );
}
