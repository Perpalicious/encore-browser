import { useState, useMemo, useEffect } from 'react';
import type { Tab, DayFilter, Density, Lot } from './lib/types';
import { filterLots } from './lib/filter';
import { sortLots } from './lib/sort';
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

export function App() {
  const [dark, toggleTheme] = useTheme();
  const [watched, toggleWatch] = usePersistedSet('encore_watched');

  const [query, setQuery] = useState('');
  const [dayFilter, setDayFilter] = useState<DayFilter>('Both');
  const [category, setCategory] = useState('All');
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

  const categories = useMemo(
    () => ['All', ...uniqueSorted(allLots.map((l) => l.category).filter(Boolean))],
    []
  );

  const batBuckets = useMemo(() => {
    const buckets: string[] = [];
    allLots.forEach((l) => {
      if (l.is_bat) l.bat_buckets.forEach((b) => buckets.push(b));
    });
    return ['All', ...uniqueSorted(buckets)];
  }, []);

  const activeFilterCount =
    (dayFilter !== 'Both' ? 1 : 0) + (category !== 'All' ? 1 : 0) + (density !== 'standard' ? 1 : 0);

  const filtered = useMemo(() => {
    const rows = filterLots(allLots, { tab, query, dayFilter, category, batBucket, watched });
    return sortLots(rows);
  }, [tab, query, dayFilter, category, batBucket, watched]);

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
    setCategory('All');
    setBatBucket('All');
    if (tab !== 'watched') setTab('all');
  };

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
        category={category}
        categories={categories}
        onCategoryChange={setCategory}
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
