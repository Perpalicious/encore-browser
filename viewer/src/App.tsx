import { useState, useMemo, useEffect } from 'react';
import { ChevronUp, FilterX, ChevronLeft } from 'lucide-react';
import type { Tab, DayFilter, Density, Bundle } from './lib/types';
import { filterLots } from './lib/filter';
import { sortLots } from './lib/sort';
import { buildCategoryTree } from './lib/categoryTree';
import { buildSearchIndex, fuzzyMatchLotNumbers } from './lib/search';
import { buildBatNav } from './lib/batNav';
import { useTheme } from './hooks/useTheme';
import { usePersistedSet } from './hooks/usePersistedSet';
import { useDebouncedValue } from './hooks/useDebouncedValue';
import { Header } from './components/Header';
import { LotGrid } from './components/LotGrid';
import { BatGroupNav } from './components/BatGroupNav';
import bundleRaw from './data/auction_bundle.json';

const bundle = bundleRaw as Bundle;
const allLots = bundle.lots;
const bucketGroups = bundle.bucket_groups;
const groupOrder = bundle.groups;

export function App() {
  const [dark, toggleTheme] = useTheme();
  const [watched, toggleWatch] = usePersistedSet('encore_watched');

  const [query, setQuery] = useState('');
  const [dayFilter, setDayFilter] = useState<DayFilter>('Both');
  const [categoryPath, setCategoryPath] = useState<string[]>([]);
  const [density, setDensity] = useState<Density>('standard');
  const [tab, setTab] = useState<Tab>('all');
  // Bat's List two-level navigation: pick a group, then a bucket. Until a
  // bucket is chosen, the grid shows nothing — the group selector drives.
  const [batGroup, setBatGroup] = useState<string | null>(null);
  const [batBucket, setBatBucket] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());
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

  // Debounce the query so the fuzzy pass over ~20k lots doesn't run per keystroke.
  const debouncedQuery = useDebouncedValue(query, 150);

  const activeFilterCount =
    (dayFilter !== 'Both' ? 1 : 0) +
    (categoryPath.length > 0 ? 1 : 0) +
    (density !== 'standard' ? 1 : 0);

  const filtered = useMemo(() => {
    const rows = filterLots(allLots, { tab, dayFilter, categoryPath, batBucket, watched });
    // Fuzzy search narrows WITHIN the structural filters — it never bypasses
    // the active tab / category / day. Intersect fuzzy matches with `rows`.
    if (debouncedQuery.trim()) {
      const matches = fuzzyMatchLotNumbers(searchIndex, debouncedQuery);
      return sortLots(rows.filter((l) => matches.has(l.lot_number)));
    }
    return sortLots(rows);
  }, [tab, debouncedQuery, dayFilter, categoryPath, batBucket, watched, searchIndex]);

  const toggleExpand = (lotNumber: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(lotNumber)) next.delete(lotNumber);
      else next.add(lotNumber);
      return next;
    });
  };

  const clearFilters = () => {
    setQuery('');
    setDayFilter('Both');
    setCategoryPath([]);
    // Tab and density are intentionally preserved.
  };

  const collapseAll = () => setExpandedIds(new Set());

  const anyFilterActive =
    query !== '' || dayFilter !== 'Both' || categoryPath.length > 0;
  const anyExpanded = expandedIds.size > 0;

  // Switching tabs resets the Bat's List drill-down to the group selector.
  const handleTabChange = (t: Tab) => {
    setTab(t);
    setBatGroup(null);
    setBatBucket(null);
  };

  // In the Bat's List tab, the group/bucket selector is shown until a bucket
  // is chosen. Everywhere else (and once a bucket is chosen) we show the grid.
  const showBatSelector = tab === 'bat' && batBucket === null;

  return (
    <div className="min-h-screen bg-paper dark:bg-night text-ink dark:text-bone">
      <Header
        dark={dark}
        onToggleTheme={toggleTheme}
        query={query}
        onQueryChange={setQuery}
        dayFilter={dayFilter}
        onDayChange={setDayFilter}
        categoryTree={categoryTree}
        categoryPath={categoryPath}
        onCategoryPathChange={setCategoryPath}
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
        {showBatSelector ? (
          <BatGroupNav
            groups={batNav}
            selectedGroup={batGroup}
            onSelectGroup={setBatGroup}
            onSelectBucket={setBatBucket}
            onBack={() => setBatGroup(null)}
          />
        ) : (
          <>
            {tab === 'bat' && batBucket !== null && (
              <div
                data-testid="bat-breadcrumb"
                className="mb-3 md:mb-4 flex items-center gap-2 flex-wrap"
              >
                <button
                  type="button"
                  data-testid="bat-back-to-buckets"
                  onClick={() => setBatBucket(null)}
                  className="inline-flex items-center gap-1 h-8 pl-2 pr-3 rounded-full text-[12px] font-medium text-ink2 dark:text-bone2 bg-paper2 dark:bg-coal hover:bg-rule dark:hover:bg-dusk ring-1 ring-rule/60 dark:ring-dusk transition-colors"
                >
                  <ChevronLeft size={15} />
                  {batGroup}
                </button>
                <span className="text-[13px] font-medium text-ink dark:text-bone">
                  {batBucket}
                </span>
                <span className="text-[11px] font-mono uppercase tracking-[0.14em] text-ink2/70 dark:text-bone2/70">
                  {filtered.length} {filtered.length === 1 ? 'lot' : 'lots'}
                </span>
              </div>
            )}

            {!loading && (anyExpanded || anyFilterActive) && (
              <div
                data-testid="grid-toolbar"
                className="mb-3 md:mb-4 flex items-center justify-between gap-3"
              >
                <span className="text-[11px] font-mono uppercase tracking-[0.14em] text-ink2/70 dark:text-bone2/70">
                  Showing {filtered.length} of {allLots.length} lots
                </span>
                <div className="flex items-center gap-1.5">
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
              expandedIds={expandedIds}
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
