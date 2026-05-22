// Main Encore Lot Browser app.

const { useState, useMemo, useEffect, useRef } = React;

// --- Helpers ---
const CONDITION_ORDER = ['New', 'Like New', 'Good', 'Fair', 'Heavily Used'];

function uniqueSorted(arr) {
  return Array.from(new Set(arr)).sort();
}

function App() {
  // Theme — default to system preference
  const [dark, setDark] = useState(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    // also color the URL bar nicely
    const meta = document.querySelector('meta[name="theme-color"]');
    const color = dark ? '#0F1012' : '#FAF6EE';
    if (meta) meta.setAttribute('content', color);
    else {
      const m = document.createElement('meta');
      m.name = 'theme-color';
      m.content = color;
      document.head.appendChild(m);
    }
  }, [dark]);

  // Filters & state
  const [query, setQuery] = useState('');
  const [dayFilter, setDayFilter] = useState('Both'); // Sunday | Monday | Both
  const [category, setCategory] = useState('All');
  const [density, setDensity] = useState('standard'); // standard | compact
  const [tab, setTab] = useState('all'); // all | bat | watched
  const [batBucket, setBatBucket] = useState('All');
  const [expandedIds, setExpandedIds] = useState(() => new Set());
  const [watched, setWatched] = useState(() => new Set());
  const [loading, setLoading] = useState(true);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const columns = useColumns(density);
  const compactMode = density === 'compact';

  // Count of active (non-default) filters — used to badge the mobile Filters button
  const activeFilterCount = (dayFilter !== 'Both' ? 1 : 0) + (category !== 'All' ? 1 : 0) + (density !== 'standard' ? 1 : 0);

  // Fake initial load
  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 900);
    return () => clearTimeout(t);
  }, []);

  // Derived: source data
  const allLots = window.LOTS;

  const categories = useMemo(() => ['All', ...uniqueSorted(allLots.map((l) => l.category))], [allLots]);
  const batBuckets = useMemo(() => {
    const buckets = [];
    allLots.forEach((l) => { if (l.is_bat) l.bat_buckets.forEach((b) => buckets.push(b)); });
    return ['All', ...uniqueSorted(buckets)];
  }, [allLots]);

  // Filter pipeline
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = allLots.slice();

    if (tab === 'watched') {
      rows = rows.filter((l) => watched.has(l.lot_number));
    } else {
      if (tab === 'bat') {
        rows = rows.filter((l) => l.is_bat);
        if (batBucket !== 'All') {
          rows = rows.filter((l) => l.bat_buckets.includes(batBucket));
        }
      }
      if (dayFilter !== 'Both') rows = rows.filter((l) => l.day === dayFilter);
      if (category !== 'All') rows = rows.filter((l) => l.category === category);
    }

    if (q) {
      rows = rows.filter((l) =>
        l.title.toLowerCase().includes(q)
        || l.description.toLowerCase().includes(q)
        || l.lot_number.toLowerCase().includes(q)
        || l.category.toLowerCase().includes(q)
        || l.subcategory.toLowerCase().includes(q)
      );
    }

    // Default sort: Bat's List first, then Sunday before Monday, then by lot_number ascending
    rows.sort((a, b) => {
      if (a.is_bat !== b.is_bat) return a.is_bat ? -1 : 1;
      if (a.day !== b.day) return a.day === 'Sunday' ? -1 : 1;
      return a.lot_number.localeCompare(b.lot_number);
    });
    return rows;
  }, [allLots, query, dayFilter, category, tab, batBucket, watched]);

  // Handlers
  const toggleWatch = (lot_number) => {
    setWatched((prev) => {
      const next = new Set(prev);
      if (next.has(lot_number)) next.delete(lot_number);
      else next.add(lot_number);
      return next;
    });
  };

  const toggleExpand = (lot_number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(lot_number)) next.delete(lot_number);
      else next.add(lot_number);
      return next;
    });
  };

  const clearFilters = () => {
    setQuery(''); setDayFilter('Both'); setCategory('All'); setBatBucket('All');
    if (tab !== 'watched') setTab('all');
  };

  // ---------- UI ----------
  return (
    <div className="min-h-screen bg-paper dark:bg-night text-ink dark:text-bone">
      {/* Sticky top bar */}
      <header className="sticky top-0 z-30 bg-paper/85 dark:bg-night/85 backdrop-blur-xl border-b border-rule dark:border-dusk supports-[backdrop-filter]:bg-paper/70 dark:supports-[backdrop-filter]:bg-night/70">
        <div className="mx-auto max-w-[1480px] px-3 md:px-6">

          {/* === MOBILE COMPACT HEADER === (hidden md+) */}
          <div className="md:hidden">
            {/* Row 1: search + filters + theme */}
            <div className="flex items-center gap-2 pt-2.5 pb-2">
              <div className="relative flex-1 min-w-0">
                <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink2/70 dark:text-bone2/70" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search lots..."
                  className="w-full h-10 pl-9 pr-9 rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk placeholder:text-ink2/60 dark:placeholder:text-bone2/60 text-[15px] focus:ring-2 focus:ring-ember focus:outline-none"
                />
                {query && (
                  <button onClick={() => setQuery('')} aria-label="Clear search"
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 grid place-items-center rounded-full hover:bg-paper2 dark:hover:bg-coal text-ink2 dark:text-bone2">
                    <X size={15} />
                  </button>
                )}
              </div>
              <button
                onClick={() => setMobileFiltersOpen((v) => !v)}
                aria-expanded={mobileFiltersOpen}
                aria-label="Filters"
                className={`relative h-10 w-10 grid place-items-center rounded-full ring-1 transition-colors
                  ${mobileFiltersOpen || activeFilterCount > 0
                    ? 'bg-ink text-paper ring-ink dark:bg-bone dark:text-night dark:ring-bone'
                    : 'bg-white dark:bg-night2 ring-rule dark:ring-dusk text-ink2 dark:text-bone2'}`}
              >
                <SlidersH size={17} />
                {activeFilterCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[16px] h-[16px] px-1 grid place-items-center rounded-full bg-ember text-white text-[10px] font-semibold ring-2 ring-paper dark:ring-night">{activeFilterCount}</span>
                )}
              </button>
              <button
                onClick={() => setDark((d) => !d)}
                aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
                className="h-10 w-10 grid place-items-center rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-ink2 dark:text-bone2"
              >
                {dark ? <Sun size={17} /> : <Moon size={17} />}
              </button>
            </div>

            {/* Row 2: tabs + count */}
            <div className="flex items-center justify-between gap-3">
              <nav className="flex items-center gap-0" aria-label="Lot view">
                <TabButton active={tab === 'all'}     onClick={() => setTab('all')}     label="All" />
                <TabButton active={tab === 'bat'}     onClick={() => setTab('bat')}     label="Bat's List" sparkle />
                <TabButton active={tab === 'watched'} onClick={() => setTab('watched')} label="Watched" badge={watched.size} />
              </nav>
              <p className="shrink-0 text-[11px] font-mono uppercase tracking-[0.12em] text-ink2 dark:text-bone2 pb-2">
                {loading ? '…' : `${filtered.length}/${allLots.length}`}
              </p>
            </div>

            {/* Collapsible filter panel */}
            <div className={`expand-grid ${mobileFiltersOpen ? 'open' : ''}`}>
              <div className="expand-inner">
                <div className="pt-1 pb-3 space-y-2 border-t border-rule/60 dark:border-dusk/60 mt-0">
                  <FilterFieldRow label="Day">
                    <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk w-full">
                      {['Sunday', 'Monday', 'Both'].map((d) => (
                        <button key={d} onClick={() => setDayFilter(d)} aria-pressed={dayFilter === d}
                          className={`flex-1 h-9 text-[13px] font-medium rounded-full transition-colors
                            ${dayFilter === d ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2'}`}>
                          {d}
                        </button>
                      ))}
                    </div>
                  </FilterFieldRow>
                  <FilterFieldRow label="Category">
                    <div className="relative w-full">
                      <select value={category} onChange={(e) => setCategory(e.target.value)}
                        className="appearance-none w-full h-10 pl-3.5 pr-9 rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-[14px] font-medium text-ink dark:text-bone focus:ring-2 focus:ring-ember focus:outline-none">
                        {categories.map((c) => <option key={c} value={c}>{c === 'All' ? 'All categories' : c}</option>)}
                      </select>
                      <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink2 dark:text-bone2" />
                    </div>
                  </FilterFieldRow>
                  <FilterFieldRow label="Density">
                    <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk w-full">
                      {[{id:'standard',label:'Standard'},{id:'compact',label:'Compact'}].map((opt) => (
                        <button key={opt.id} onClick={() => setDensity(opt.id)} aria-pressed={density === opt.id}
                          className={`flex-1 h-9 text-[13px] font-medium rounded-full transition-colors
                            ${density === opt.id ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2'}`}>
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </FilterFieldRow>
                </div>
              </div>
            </div>
          </div>

          {/* === DESKTOP HEADER === (hidden < md) */}
          <div className="hidden md:block">
            <div className="flex items-center gap-3 pt-3 pb-2.5">
              <a href="#" className="group inline-flex items-baseline gap-2 select-none mr-1 shrink-0">
                <span className="font-serif italic text-[22px] leading-none text-ink dark:text-bone tracking-tight">Encore</span>
                <span className="font-mono text-[10px] tracking-[0.22em] uppercase text-ink2 dark:text-bone2">Lot Browser</span>
              </a>

              <div className="relative flex-1 min-w-0 max-w-xl">
                <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink2/70 dark:text-bone2/70" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search lots..."
                  className="w-full h-10 pl-10 pr-10 rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk placeholder:text-ink2/60 dark:placeholder:text-bone2/60 text-[14px] focus:ring-2 focus:ring-ember focus:outline-none"
                />
                {query && (
                  <button onClick={() => setQuery('')} aria-label="Clear search"
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 grid place-items-center rounded-full hover:bg-paper2 dark:hover:bg-coal text-ink2 dark:text-bone2">
                    <X size={15} />
                  </button>
                )}
              </div>

              <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk shrink-0">
                {['Sunday', 'Monday', 'Both'].map((d) => (
                  <button key={d} onClick={() => setDayFilter(d)} aria-pressed={dayFilter === d}
                    className={`px-3 h-[34px] text-[13px] font-medium rounded-full transition-colors
                      ${dayFilter === d ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'}`}>
                    {d}
                  </button>
                ))}
              </div>

              <div className="relative shrink-0">
                <select value={category} onChange={(e) => setCategory(e.target.value)}
                  className="appearance-none h-10 pl-3.5 pr-9 rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-[13px] font-medium text-ink dark:text-bone focus:ring-2 focus:ring-ember focus:outline-none cursor-pointer">
                  {categories.map((c) => <option key={c} value={c}>{c === 'All' ? 'All categories' : c}</option>)}
                </select>
                <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink2 dark:text-bone2" />
              </div>

              <div className="inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk shrink-0">
                {[{id:'standard',label:'Standard'},{id:'compact',label:'Compact'}].map((opt) => (
                  <button key={opt.id} onClick={() => setDensity(opt.id)} aria-pressed={density === opt.id}
                    className={`px-3 h-[34px] text-[13px] font-medium rounded-full transition-colors
                      ${density === opt.id ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone' : 'text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'}`}>
                    {opt.label}
                  </button>
                ))}
              </div>

              <button onClick={() => setDark((d) => !d)}
                aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
                className="h-10 w-10 grid place-items-center rounded-full hover:bg-paper2 dark:hover:bg-coal text-ink2 dark:text-bone2 shrink-0">
                {dark ? <Sun size={18} /> : <Moon size={18} />}
              </button>
            </div>

            <div className="flex items-center justify-between gap-3">
              <nav className="flex items-end gap-0" aria-label="Lot view">
                <TabButton active={tab === 'all'}     onClick={() => setTab('all')}     label="All" />
                <TabButton active={tab === 'bat'}     onClick={() => setTab('bat')}     label="Bat's List" sparkle />
                <TabButton active={tab === 'watched'} onClick={() => setTab('watched')} label="Watched" badge={watched.size} />
              </nav>
              <p className="text-[12px] font-mono uppercase tracking-[0.14em] text-ink2 dark:text-bone2 pb-2">
                {loading ? 'Loading…' : `Showing ${filtered.length} of ${allLots.length} lots`}
              </p>
            </div>
          </div>

          {/* Bat-bucket chip row (only when Bat's List tab active) */}
          {tab === 'bat' && !loading && (
            <div className="-mx-4 md:-mx-6 px-4 md:px-6 pt-3 pb-3 border-t border-rule/60 dark:border-dusk/60 animate-slideDown">
              <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
                {batBuckets.map((b) => (
                  <button
                    key={b}
                    onClick={() => setBatBucket(b)}
                    aria-pressed={batBucket === b}
                    className={`shrink-0 inline-flex items-center gap-1.5 h-9 px-3.5 rounded-full text-[13px] font-medium transition-all
                      ${batBucket === b
                        ? 'bg-ink text-paper dark:bg-bone dark:text-night'
                        : 'bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'}`}
                  >
                    {batBucket === b && b !== 'All' && <Check size={13} strokeWidth={2.5} />}
                    {b}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Main grid */}
      <main className="mx-auto max-w-[1480px] px-4 md:px-6 pt-4 md:pt-6 pb-24">
        {loading ? (
          <div className={`grid gap-4 md:gap-5 ${density === 'compact' ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'}`}>
            {Array.from({ length: 8 }).map((_, i) => (
              <SkeletonCard key={i} density={density} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState tab={tab} onClear={clearFilters} />
        ) : (
          <div className={`grid gap-4 md:gap-5 ${compactMode ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'}`}>
            {(() => {
              if (!compactMode) {
                // Standard mode: in-card inline expand
                return filtered.map((lot) => (
                  <LotCard
                    key={lot.lot_number}
                    lot={lot}
                    expanded={expandedIds.has(lot.lot_number)}
                    onToggleExpand={() => toggleExpand(lot.lot_number)}
                    watched={watched.has(lot.lot_number)}
                    onToggleWatch={() => toggleWatch(lot.lot_number)}
                    density={density}
                  />
                ));
              }
              // Compact mode: chunk by columns, after any row with expanded card(s) insert full-row panels
              const out = [];
              for (let i = 0; i < filtered.length; i += columns) {
                const row = filtered.slice(i, i + columns);
                row.forEach((lot) => {
                  out.push(
                    <LotCard
                      key={lot.lot_number}
                      lot={lot}
                      expanded={expandedIds.has(lot.lot_number)}
                      onToggleExpand={() => toggleExpand(lot.lot_number)}
                      watched={watched.has(lot.lot_number)}
                      onToggleWatch={() => toggleWatch(lot.lot_number)}
                      density={density}
                      inlineExpand={false}
                    />
                  );
                });
                row.forEach((lot) => {
                  if (expandedIds.has(lot.lot_number)) {
                    out.push(
                      <LotExpandPanel
                        key={`exp-${lot.lot_number}`}
                        lot={lot}
                        fullRow
                        onCollapse={() => toggleExpand(lot.lot_number)}
                      />
                    );
                  }
                });
              }
              return out;
            })()}
          </div>
        )}

        {/* Footnote */}
        {!loading && filtered.length > 0 && (
          <p className="mt-12 text-center text-[11px] font-mono uppercase tracking-[0.18em] text-ink2/60 dark:text-bone2/60">
            End of lots · {filtered.length} shown
          </p>
        )}
      </main>
    </div>
  );
}

// ---------- Column-count hook (Tailwind breakpoint aware) ----------
function useColumns(density) {
  const get = () => {
    if (typeof window === 'undefined') return 1;
    const w = window.innerWidth;
    if (density === 'compact') {
      if (w >= 1280) return 5;
      if (w >= 1024) return 4;
      if (w >= 640)  return 3;
      return 2;
    } else {
      if (w >= 1280) return 4;
      if (w >= 1024) return 3;
      if (w >= 640)  return 2;
      return 1;
    }
  };
  const [cols, setCols] = useState(get);
  useEffect(() => {
    const onResize = () => setCols(get());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [density]);
  return cols;
}

// ---------- Mobile filter field row ----------
function FilterFieldRow({ label, children }) {
  return (
    <div className="flex items-center gap-3">
      <span className="shrink-0 w-[68px] text-[11px] font-mono uppercase tracking-[0.14em] text-ink2 dark:text-bone2">{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

// ---------- Tab button ----------
function TabButton({ active, onClick, label, badge, sparkle }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`relative inline-flex items-center gap-1.5 h-11 px-3 md:px-4 text-[14px] md:text-[15px] font-medium transition-colors
        ${active
          ? 'text-ink dark:text-bone'
          : 'text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'}`}
      style={{ height: 40 }}
    >
      {sparkle && (
        <Sparkle size={14} className={active ? 'text-ember' : 'text-ember/70'} strokeWidth={2} />
      )}
      <span>{label}</span>
      {typeof badge === 'number' && (
        <span className={`inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-semibold tabular-nums
          ${active
            ? 'bg-ember text-white'
            : 'bg-paper2 dark:bg-coal text-ink2 dark:text-bone2'}`}>
          {badge}
        </span>
      )}
      {/* underline indicator */}
      <span
        className={`absolute left-2 right-2 -bottom-px h-[2px] rounded-full transition-all duration-200
          ${active ? 'bg-ember opacity-100' : 'opacity-0 bg-ember'}`}
      />
    </button>
  );
}

// ---------- Empty state ----------
function EmptyState({ tab, onClear }) {
  const copy =
    tab === 'watched'
      ? { title: 'No watched lots yet', body: 'Tap the star on any card to keep an eye on it. Watched lots stay here even when filters change.' }
      : tab === 'bat'
      ? { title: 'No matches in Bat\'s List', body: 'Try a different bucket — or clear the filters to see everything.' }
      : { title: 'Nothing matches those filters', body: 'Loosen the search, switch days, or pick a different category.' };

  return (
    <div className="mx-auto max-w-md text-center py-20 md:py-28">
      <div className="mx-auto mb-5 h-14 w-14 grid place-items-center rounded-full bg-paper2 dark:bg-coal text-ember">
        <Sparkle size={24} strokeWidth={1.75} />
      </div>
      <h2 className="font-serif text-[26px] leading-tight text-ink dark:text-bone">{copy.title}</h2>
      <p className="mt-2 text-[14px] text-ink2 dark:text-bone2 leading-relaxed">{copy.body}</p>
      {tab !== 'watched' && (
        <button
          onClick={onClear}
          className="mt-6 inline-flex items-center gap-2 h-11 px-5 rounded-full bg-ember hover:bg-ember2 text-white font-medium text-[14px]"
        >
          <X size={16} />
          Clear filters
        </button>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
