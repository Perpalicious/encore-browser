import { Search, X, Sun, Moon, SlidersHorizontal } from 'lucide-react';
import type { Tab, DayFilter, Density, ConfidenceFilter } from '../lib/types';
import type { CatNode } from '../lib/categoryTree';
import { TabButton } from './TabButton';
import { FilterFieldRow } from './FilterFieldRow';
import { CategoryFilter } from './CategoryFilter';
import { ResaleFilter } from './ResaleFilter';

interface Props {
  dark: boolean;
  onToggleTheme: () => void;
  query: string;
  onQueryChange: (q: string) => void;
  dayFilter: DayFilter;
  onDayChange: (d: DayFilter) => void;
  categoryTree: CatNode;
  categoryPath: string[];
  onCategoryPathChange: (p: string[]) => void;
  confidenceFilter: ConfidenceFilter;
  onConfidenceChange: (c: ConfidenceFilter) => void;
  potentialOnly: boolean;
  onPotentialToggle: () => void;
  density: Density;
  onDensityChange: (d: Density) => void;
  tab: Tab;
  onTabChange: (t: Tab) => void;
  watchedCount: number;
  filteredCount: number;
  totalCount: number;
  loading: boolean;
  mobileFiltersOpen: boolean;
  onToggleMobileFilters: () => void;
  activeFilterCount: number;
}

export function Header({
  dark,
  onToggleTheme,
  query,
  onQueryChange,
  dayFilter,
  onDayChange,
  categoryTree,
  categoryPath,
  onCategoryPathChange,
  confidenceFilter,
  onConfidenceChange,
  potentialOnly,
  onPotentialToggle,
  density,
  onDensityChange,
  tab,
  onTabChange,
  watchedCount,
  filteredCount,
  totalCount,
  loading,
  mobileFiltersOpen,
  onToggleMobileFilters,
  activeFilterCount,
}: Props) {
  return (
    <header className="sticky top-0 z-30 bg-paper/85 dark:bg-night/85 backdrop-blur-xl border-b border-rule dark:border-dusk supports-[backdrop-filter]:bg-paper/70 dark:supports-[backdrop-filter]:bg-night/70">
      <div className="mx-auto max-w-[1480px] px-3 md:px-6">
        {/* === MOBILE HEADER === */}
        <div className="md:hidden">
          {/* Row 1: search + filters + theme */}
          <div className="flex items-center gap-2 pt-2.5 pb-2">
            <div className="relative flex-1 min-w-0">
              <Search
                size={17}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-ink2/70 dark:text-bone2/70"
              />
              <input
                type="search"
                data-testid="search-input"
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                placeholder="Search lots..."
                className="w-full h-10 pl-9 pr-9 rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk placeholder:text-ink2/60 dark:placeholder:text-bone2/60 text-[15px] focus:ring-2 focus:ring-ember focus:outline-none"
              />
              {query && (
                <button
                  onClick={() => onQueryChange('')}
                  aria-label="Clear search"
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 grid place-items-center rounded-full hover:bg-paper2 dark:hover:bg-coal text-ink2 dark:text-bone2"
                >
                  <X size={15} />
                </button>
              )}
            </div>
            <button
              onClick={onToggleMobileFilters}
              aria-expanded={mobileFiltersOpen}
              aria-label="Filters"
              className={`relative h-10 w-10 grid place-items-center rounded-full ring-1 transition-colors
                ${
                  mobileFiltersOpen || activeFilterCount > 0
                    ? 'bg-ink text-paper ring-ink dark:bg-bone dark:text-night dark:ring-bone'
                    : 'bg-white dark:bg-night2 ring-rule dark:ring-dusk text-ink2 dark:text-bone2'
                }`}
            >
              <SlidersHorizontal size={17} />
              {activeFilterCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[16px] h-[16px] px-1 grid place-items-center rounded-full bg-ember text-white text-[10px] font-semibold ring-2 ring-paper dark:ring-night">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <button
              onClick={onToggleTheme}
              aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="h-10 w-10 grid place-items-center rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-ink2 dark:text-bone2"
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>

          {/* Row 2: tabs + count */}
          <div className="flex items-center justify-between gap-3">
            <nav className="flex items-center gap-0" aria-label="Lot view">
              <TabButton
                active={tab === 'all'}
                onClick={() => onTabChange('all')}
                label="All"
                testId="tab-all"
              />
              <TabButton
                active={tab === 'bat'}
                onClick={() => onTabChange('bat')}
                label="Bat's List"
                sparkle
                testId="tab-bat"
              />
              <TabButton
                active={tab === 'watched'}
                onClick={() => onTabChange('watched')}
                label="Watched"
                badge={watchedCount}
                testId="tab-watched"
              />
            </nav>
            <p data-testid="result-count" className="shrink-0 text-[11px] font-mono uppercase tracking-[0.12em] text-ink2 dark:text-bone2 pb-2">
              {loading ? '…' : `${filteredCount}/${totalCount}`}
            </p>
          </div>

          {/* Collapsible filter panel */}
          <div className={`expand-grid ${mobileFiltersOpen ? 'open' : ''}`}>
            <div className="expand-inner">
              <div className="pt-1 pb-3 space-y-2 border-t border-rule/60 dark:border-dusk/60 mt-0">
                <FilterFieldRow label="Day">
                  <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk w-full">
                    {(['Sunday', 'Monday', 'Both'] as DayFilter[]).map((d) => (
                      <button
                        key={d}
                        onClick={() => onDayChange(d)}
                        aria-pressed={dayFilter === d}
                        className={`flex-1 h-9 text-[13px] font-medium rounded-full transition-colors
                            ${dayFilter === d ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2'}`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </FilterFieldRow>
                <FilterFieldRow label="Category">
                  <CategoryFilter
                    tree={categoryTree}
                    selected={categoryPath}
                    onChange={onCategoryPathChange}
                    size="md"
                  />
                </FilterFieldRow>
                <FilterFieldRow label="Resale">
                  <ResaleFilter
                    confidenceFilter={confidenceFilter}
                    onConfidenceChange={onConfidenceChange}
                    potentialOnly={potentialOnly}
                    onPotentialToggle={onPotentialToggle}
                    size="md"
                  />
                </FilterFieldRow>
                <FilterFieldRow label="Density">
                  <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk w-full">
                    {([{ id: 'standard', label: 'Standard' }, { id: 'compact', label: 'Compact' }] as { id: Density; label: string }[]).map((opt) => (
                      <button
                        key={opt.id}
                        onClick={() => onDensityChange(opt.id)}
                        aria-pressed={density === opt.id}
                        className={`flex-1 h-9 text-[13px] font-medium rounded-full transition-colors
                            ${density === opt.id ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2'}`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </FilterFieldRow>
              </div>
            </div>
          </div>
        </div>

        {/* === DESKTOP HEADER === */}
        <div className="hidden md:block">
          <div className="flex items-center gap-3 pt-3 pb-2.5">
            <a
              href="#"
              className="group inline-flex items-baseline gap-2 select-none mr-1 shrink-0"
            >
              <span className="font-serif italic text-[22px] leading-none text-ink dark:text-bone tracking-tight">
                Encore
              </span>
              <span className="font-mono text-[10px] tracking-[0.22em] uppercase text-ink2 dark:text-bone2">
                Lot Browser
              </span>
            </a>

            <div className="relative flex-1 min-w-0 max-w-xl">
              <Search
                size={18}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink2/70 dark:text-bone2/70"
              />
              <input
                type="search"
                data-testid="search-input"
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                placeholder="Search lots..."
                className="w-full h-10 pl-10 pr-10 rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk placeholder:text-ink2/60 dark:placeholder:text-bone2/60 text-[14px] focus:ring-2 focus:ring-ember focus:outline-none"
              />
              {query && (
                <button
                  onClick={() => onQueryChange('')}
                  aria-label="Clear search"
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 grid place-items-center rounded-full hover:bg-paper2 dark:hover:bg-coal text-ink2 dark:text-bone2"
                >
                  <X size={15} />
                </button>
              )}
            </div>

            <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk shrink-0">
              {(['Sunday', 'Monday', 'Both'] as DayFilter[]).map((d) => (
                <button
                  key={d}
                  onClick={() => onDayChange(d)}
                  aria-pressed={dayFilter === d}
                  className={`px-3 h-[34px] text-[13px] font-medium rounded-full transition-colors
                      ${dayFilter === d ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'}`}
                >
                  {d}
                </button>
              ))}
            </div>

            <CategoryFilter
              tree={categoryTree}
              selected={categoryPath}
              onChange={onCategoryPathChange}
              size="sm"
            />

            <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk shrink-0">
              {([{ id: 'standard', label: 'Standard' }, { id: 'compact', label: 'Compact' }] as { id: Density; label: string }[]).map(
                (opt) => (
                  <button
                    key={opt.id}
                    onClick={() => onDensityChange(opt.id)}
                    aria-pressed={density === opt.id}
                    className={`px-3 h-[34px] text-[13px] font-medium rounded-full transition-colors
                        ${density === opt.id ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'}`}
                  >
                    {opt.label}
                  </button>
                )
              )}
            </div>

            <button
              onClick={onToggleTheme}
              aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="h-10 w-10 grid place-items-center rounded-full hover:bg-paper2 dark:hover:bg-coal text-ink2 dark:text-bone2 shrink-0"
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>

          {/* Row 2: tabs + count */}
          <div className="flex items-center justify-between gap-3">
            <nav className="flex items-end gap-0" aria-label="Lot view">
              <TabButton
                active={tab === 'all'}
                onClick={() => onTabChange('all')}
                label="All"
                testId="tab-all"
              />
              <TabButton
                active={tab === 'bat'}
                onClick={() => onTabChange('bat')}
                label="Bat's List"
                sparkle
                testId="tab-bat"
              />
              <TabButton
                active={tab === 'watched'}
                onClick={() => onTabChange('watched')}
                label="Watched"
                badge={watchedCount}
                testId="tab-watched"
              />
            </nav>
            <div className="flex items-center gap-3 pb-2">
              <ResaleFilter
                confidenceFilter={confidenceFilter}
                onConfidenceChange={onConfidenceChange}
                potentialOnly={potentialOnly}
                onPotentialToggle={onPotentialToggle}
                size="sm"
              />
              <p data-testid="result-count" className="text-[12px] font-mono uppercase tracking-[0.14em] text-ink2 dark:text-bone2 whitespace-nowrap">
                {loading ? 'Loading…' : `Showing ${filteredCount} of ${totalCount} lots`}
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
