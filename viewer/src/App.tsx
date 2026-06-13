import { useState, useMemo, useEffect } from 'react';
import { ChevronUp, FilterX, Sparkles } from 'lucide-react';
import type {
  Tab,
  DayFilter,
  Density,
  Bundle,
  ConfidenceFilter,
  SortKey,
  Condition,
} from './lib/types';
import { CONDITION_ORDER } from './lib/types';
import { filterLots } from './lib/filter';
import { sortLots } from './lib/sort';
import { buildCategoryTree } from './lib/categoryTree';
import { buildSearchIndex, searchLotNumbers } from './lib/search';
import { buildBatNav } from './lib/batNav';
import { useTheme } from './hooks/useTheme';
import { usePersistedSet } from './hooks/usePersistedSet';
import { useDebouncedValue } from './hooks/useDebouncedValue';
import { Header } from './components/Header';
import { LotGrid } from './components/LotGrid';
import { BatBucketSelect } from './components/BatBucketSelect';
import { ItemControls } from './components/ItemControls';
import bundleRaw from './data/auction_bundle.json';

const bundle = bundleRaw as Bundle;
const allLots = bundle.lots;
const bucketGroups = bundle.bucket_groups;
const groupOrder = bundle.groups;

export function App() {
  const [dark, toggleTheme] = useTheme();
  const [watched, toggleWatch] = usePersistedSet('encore_watched');

  const [query, setQuery] = useState('');
  // Search is EXACT (substring) by default; this opts into typo-tolerant fuzzy
  // matching. Session-only (no persistence), default off on load.
  const [fuzzy, setFuzzy] = useState(false);
  const [dayFilter, setDayFilter] = useState<DayFilter>('Both');
  const [categoryPath, setCategoryPath] = useState<string[]>([]);
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>('all');
  const [potentialOnly, setPotentialOnly] = useState(false);
  const [density, setDensity] = useState<Density>('standard');
  const [tab, setTab] = useState<Tab>('all');
  // Bat's List: a single grouped dropdown picks the bucket. Null = nothing
  // picked yet (we prompt rather than flood the grid with thousands of lots).
  // Remembered for the session so switching tabs and back keeps your place.
  const [batBucket, setBatBucket] = useState<string | null>(null);
  // Sort order + condition chips apply to whatever lots are currently shown.
  const [sortKey, setSortKey] = useState<SortKey>('lot');
  const [conditions, setConditions] = useState<Set<Condition>>(new Set());
  // Single-accordion: at most one card is expanded at a time.
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  // Fake initial load skeleton for 900ms
  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 900);
    return () => clearTimeout(t);
  }, []);

  // Build the HiBid category hierarchy, fuzzy search index, and Bat's List
  // group→bucket tree once on load.
  const categoryTree = useMemo(() => buildCategoryTree(allLots), []);
  const searchIndex = useMemo(() => buildSearchIndex(allLots), []);
  const batNav = useMemo(
    () => buildBatNav(allLots, bucketGroups, groupOrder),
    []
  );

  // Condition values actually present in the data, in canonical order.
  const availableConditions = useMemo<Condition[]>(() => {
    const present = new Set<Condition>();
    for (const l of allLots) if (l.condition !== null) present.add(l.condition);
    return CONDITION_ORDER.filter((c) => present.has(c));
  }, []);

  // Debounce the query so the fuzzy pass over ~20k lots doesn't run per keystroke.
  const debouncedQuery = useDebouncedValue(query, 150);

  const activeFilterCount =
    (dayFilter !== 'Both' ? 1 : 0) +
    (categoryPath.length > 0 ? 1 : 0) +
    (confidenceFilter !== 'all' ? 1 : 0) +
    (potentialOnly ? 1 : 0) +
    (conditions.size > 0 ? 1 : 0) +
    (density !== 'standard' ? 1 : 0);

  const filtered = useMemo(() => {
    const rows = filterLots(allLots, {
      tab,
      dayFilter,
      categoryPath,
      batBucket,
      watched,
      confidenceFilter,
      potentialOnly,
      conditions,
    });
    // Search narrows WITHIN the structural filters — it never bypasses the
    // active tab / category / day. Intersect matches with `rows`.
    if (debouncedQuery.trim()) {
      const matches = searchLotNumbers(searchIndex, debouncedQuery, fuzzy);
      return sortLots(rows.filter((l) => matches.has(l.lot_number)), sortKey);
    }
    return sortLots(rows, sortKey);
  }, [tab, debouncedQuery, fuzzy, dayFilter, categoryPath, batBucket, watched, confidenceFilter, potentialOnly, conditions, sortKey, searchIndex]);

  // Single-accordion: opening a card collapses any other open card; toggling
  // the open card closes it (so zero open is possible).
  const toggleExpand = (lotNumber: string) => {
    setExpandedId((prev) => (prev === lotNumber ? null : lotNumber));
  };

  const toggleCondition = (c: Condition) => {
    setConditions((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  };

  const clearFilters = () => {
    setQuery('');
    setDayFilter('Both');
    setCategoryPath([]);
    setConfidenceFilter('all');
    setPotentialOnly(false);
    setConditions(new Set());
    // Tab, density, and sort order are intentionally preserved.
  };

  const collapseAll = () => setExpandedId(null);

  const anyFilterActive =
    query !== '' ||
    dayFilter !== 'Both' ||
    categoryPath.length > 0 ||
    confidenceFilter !== 'all' ||
    potentialOnly ||
    conditions.size > 0;
  const anyExpanded = expandedId !== null;

  const handleTabChange = (t: Tab) => {
    setTab(t);
  };

  // Bat's List prompts for a bucket via the dropdown; until one is picked we
  // show the prompt instead of the grid (no thousands-of-items flood).
  const showBatPrompt = tab === 'bat' && batBucket === null;
  // The sort + condition controls ride above any item grid (every tab once a
  // grid is shown), but not over the Bat's List "pick a bucket" prompt.
  const showItemControls = !loading && !showBatPrompt;

  return (
    <div className="min-h-screen bg-paper dark:bg-night text-ink dark:text-bone">
      <Header
        dark={dark}
        onToggleTheme={toggleTheme}
        query={query}
        onQueryChange={setQuery}
        fuzzy={fuzzy}
        onFuzzyToggle={() => setFuzzy((v) => !v)}
        dayFilter={dayFilter}
        onDayChange={setDayFilter}
        categoryTree={categoryTree}
        categoryPath={categoryPath}
        onCategoryPathChange={setCategoryPath}
        confidenceFilter={confidenceFilter}
        onConfidenceChange={setConfidenceFilter}
        potentialOnly={potentialOnly}
        onPotentialToggle={() => setPotentialOnly((v) => !v)}
        density={density}
        onDensityChange={setDensity}
        tab={tab}
        onTabChange={handleTabChange}
        watchedCount={watched.size}
        filteredCount={filtered.length}
        totalCount={allLots.length}
        loading={loading}
        mobileFiltersOpen={mobileFiltersOpen}
        onToggleMobileFilters={() => setMobileFiltersOpen((v) => !v)}
        activeFilterCount={activeFilterCount}
      />

      <main className="mx-auto max-w-[1480px] px-4 md:px-6 pt-4 md:pt-6 pb-24">
        {/* Bat's List bucket picker — always shown on the Bat's List tab so you
            can switch buckets in one action, no drill-in / back-out. */}
        {tab === 'bat' && (
          <div className="mb-3 md:mb-4">
            <BatBucketSelect
              groups={batNav}
              value={batBucket}
              onChange={setBatBucket}
            />
          </div>
        )}

        {showBatPrompt ? (
          <div
            data-testid="bat-prompt"
            className="mx-auto max-w-md text-center py-20 md:py-28"
          >
            <div className="mx-auto mb-5 h-14 w-14 grid place-items-center rounded-full bg-paper2 dark:bg-coal text-ember">
              <Sparkles size={24} strokeWidth={1.75} />
            </div>
            <h2 className="font-serif text-[26px] leading-tight text-ink dark:text-bone">
              Pick a bucket
            </h2>
            <p className="mt-2 text-[14px] text-ink2 dark:text-bone2 leading-relaxed">
              Choose a bucket from the dropdown above to see Bat's curated lots.
            </p>
          </div>
        ) : (
          <>
            {/* Sort + condition controls, plus collapse/clear actions. */}
            {showItemControls && (
              <div
                data-testid="grid-toolbar"
                className="mb-3 md:mb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-2 md:gap-3"
              >
                <ItemControls
                  sortKey={sortKey}
                  onSortChange={setSortKey}
                  conditions={conditions}
                  onToggleCondition={toggleCondition}
                  availableConditions={availableConditions}
                />
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="mr-1 text-[11px] font-mono uppercase tracking-[0.14em] text-ink2/70 dark:text-bone2/70 whitespace-nowrap">
                    {filtered.length} {filtered.length === 1 ? 'lot' : 'lots'}
                  </span>
                  {anyExpanded && (
                    <button
                      type="button"
                      data-testid="collapse-all-btn"
                      onClick={collapseAll}
                      className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-[12px] font-medium text-ink2 dark:text-bone2 bg-paper2 dark:bg-coal hover:bg-rule dark:hover:bg-dusk ring-1 ring-rule/60 dark:ring-dusk transition-colors"
                    >
                      <ChevronUp size={14} strokeWidth={2} />
                      <span>Collapse all</span>
                    </button>
                  )}
                  {anyFilterActive && (
                    <button
                      type="button"
                      data-testid="clear-filters-btn"
                      onClick={clearFilters}
                      className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-[12px] font-medium text-ink2 dark:text-bone2 bg-paper2 dark:bg-coal hover:bg-rule dark:hover:bg-dusk ring-1 ring-rule/60 dark:ring-dusk transition-colors"
                    >
                      <FilterX size={14} strokeWidth={2} />
                      <span>Clear filters</span>
                    </button>
                  )}
                </div>
              </div>
            )}
            <LotGrid
              lots={filtered}
              loading={loading}
              density={density}
              tab={tab}
              expandedId={expandedId}
              watched={watched}
              onToggleExpand={toggleExpand}
              onToggleWatch={toggleWatch}
              onClearFilters={clearFilters}
            />
          </>
        )}
      </main>
    </div>
  );
}
