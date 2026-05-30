import { useState, useMemo, useEffect } from 'react';
import { ChevronUp, FilterX } from 'lucide-react';
import type { Tab, DayFilter, Density, Lot } from './lib/types';
import { filterLots } from './lib/filter';
import { sortLots } from './lib/sort';
import { buildCategoryTree } from './lib/categoryTree';
import { useTheme } from './hooks/useTheme';
import { usePersistedSet } from './hooks/usePersistedSet';
import { Header } from './components/Header';
import { LotGrid } from './components/LotGrid';
import bundleRaw from './data/auction_bundle.json';

// Cast the JSON import to Lot[]
const allLots = bundleRaw as Lot[];

function uniqueSorted(arr: string[]): string[] {
  return Array.from(new Set(arr)).sort();
}

function substringSearch(lots: Lot[], query: string): Lot[] {
  const q = query.trim().toLowerCase();
  if (!q) return lots;
  return lots.filter(
    (l) =>
      l.title.toLowerCase().includes(q) ||
      l.description.toLowerCase().includes(q) ||
      l.lot_number.toLowerCase().includes(q) ||
      l.category_path.some((c) => c.toLowerCase().includes(q)) ||
      l.subcategory.toLowerCase().includes(q)
  );
}

export function App() {
  const [dark, toggleTheme] = useTheme();
  const [watched, toggleWatch] = usePersistedSet('encore_watched');

  const [query, setQuery] = useState('');
  const [dayFilter, setDayFilter] = useState<DayFilter>('Both');
  const [categoryPath, setCategoryPath] = useState<string[]>([]);
  const [density, setDensity] = useState<Density>('standard');
  const [tab, setTab] = useState<Tab>('all');
  const [batBucket, setBatBucket] = useState('All');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  // Fake initial load skeleton for 900ms
  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 900);
    return () => clearTimeout(t);
  }, []);

  // Build the HiBid category hierarchy once from the loaded bundle.
  const categoryTree = useMemo(() => buildCategoryTree(allLots), []);

  const batBuckets = useMemo(() => {
    const buckets: string[] = [];
    allLots.forEach((l) => {
      if (l.is_bat) l.bat_buckets.forEach((b) => buckets.push(b));
    });
    return ['All', ...uniqueSorted(buckets)];
  }, []);

  const activeFilterCount =
    (dayFilter !== 'Both' ? 1 : 0) +
    (categoryPath.length > 0 ? 1 : 0) +
    (density !== 'standard' ? 1 : 0);

  const filtered = useMemo(() => {
    const rows = filterLots(allLots, { tab, dayFilter, categoryPath, batBucket, watched });
    const searched = substringSearch(rows, query);
    return sortLots(searched);
  }, [tab, query, dayFilter, categoryPath, batBucket, watched]);

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
    setBatBucket('All');
    // Tab and density are intentionally preserved.
  };

  const collapseAll = () => setExpandedIds(new Set());

  const anyFilterActive =
    query !== '' || dayFilter !== 'Both' || categoryPath.length > 0 || batBucket !== 'All';
  const anyExpanded = expandedIds.size > 0;

  // When tab changes, reset bucket
  const handleTabChange = (t: Tab) => {
    setTab(t);
    setBatBucket('All');
  };

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
        batBuckets={batBuckets}
        batBucket={batBucket}
        onBatBucketChange={setBatBucket}
        mobileFiltersOpen={mobileFiltersOpen}
        onToggleMobileFilters={() => setMobileFiltersOpen((v) => !v)}
        activeFilterCount={activeFilterCount}
      />

      <main className="mx-auto max-w-[1480px] px-4 md:px-6 pt-4 md:pt-6 pb-24">
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
      </main>
    </div>
  );
}
