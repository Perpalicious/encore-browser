import { useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { Tab, SortKey, ViewMode } from '../lib/types';

/**
 * The sticky header — docs/design/README.md § "Sticky header".
 *
 * Two rows. Row 1 is identity and search. Row 2 is the RAIL, and it is the row
 * that must never leave the viewport: everything that was a CONTROL is behind
 * one of three buttons (category, sort, filters), and everything that was STATE
 * is a removable chip. Nothing is hidden — you can always see what you filtered.
 *
 * Unlike the header this replaces, there is ONE markup tree, not a `md:hidden`
 * mobile copy beside a `hidden md:block` desktop copy. Sizes and which pieces
 * appear are driven by the `mobile` prop.
 */

export interface ActiveChip {
  /** Stable key, also the test id suffix. */
  id: string;
  label: string;
  onRemove: () => void;
}

interface Props {
  mobile: boolean;
  dark: boolean;
  onToggleTheme: () => void;
  query: string;
  onQueryChange: (q: string) => void;
  fuzzy: boolean;
  onFuzzyToggle: () => void;
  tab: Tab;
  onTabChange: (t: Tab) => void;
  watchedCount: number;
  filteredCount: number;
  totalCount: number;
  loading: boolean;
  /** Rail: category button label + open handler. */
  categoryLabel: string;
  categoryActive: boolean;
  onOpenCategory: () => void;
  sortKey: SortKey;
  onCycleSort: () => void;
  onOpenFilters: () => void;
  activeFilterCount: number;
  chips: ActiveChip[];
  onClearAll: () => void;
  searchRef?: React.RefObject<HTMLInputElement>;
  view: ViewMode;
  onViewChange: (v: ViewMode) => void;
  /** Jump-to-lot: fired on Enter with whatever was typed. */
  onJump: (raw: string) => void;
  /** Touch device: the hint line advertises swipe rather than the key map. */
  coarse: boolean;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

const SORT_LABEL: Record<SortKey, string> = {
  lot: 'Lot number',
  'resale-desc': 'Resale ↓',
  'resale-asc': 'Resale ↑',
  'retail-desc': 'Retail ↓',
};

const TABS: { id: Tab; label: string; testId: string }[] = [
  { id: 'all', label: 'All', testId: 'tab-all' },
  { id: 'bat', label: '✦ Bat’s List', testId: 'tab-bat' },
  { id: 'watched', label: 'Watched', testId: 'tab-watched' },
];

const railButton: CSSProperties = {
  height: 30,
  padding: '0 11px',
  borderRadius: 8,
  background: 'var(--s2)',
  border: '1px solid var(--line)',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  fontSize: '11.5px',
  fontWeight: 500,
  color: 'var(--dim)',
  flex: 'none',
  maxWidth: 240,
};

export function Header({
  mobile,
  dark,
  onToggleTheme,
  query,
  onQueryChange,
  fuzzy,
  onFuzzyToggle,
  tab,
  onTabChange,
  watchedCount,
  filteredCount,
  totalCount,
  loading,
  categoryLabel,
  categoryActive,
  onOpenCategory,
  sortKey,
  onCycleSort,
  onOpenFilters,
  activeFilterCount,
  chips,
  onClearAll,
  searchRef,
  view,
  onViewChange,
  onJump,
  coarse,
}: Props) {
  // Ephemeral: what you typed to get somewhere is not part of the view, so it
  // is neither lifted to App nor persisted to the hash.
  const [jump, setJump] = useState('');

  const jumpField = (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 7,
        height: 32,
        padding: '0 10px',
        borderRadius: 8,
        background: 'var(--s2)',
        border: '1px solid var(--line)',
        flex: 'none',
      }}
    >
      <label
        htmlFor="jump-to-lot"
        style={{
          fontFamily: MONO,
          fontWeight: 500,
          fontSize: '8.5px',
          lineHeight: 1,
          letterSpacing: '.12em',
          color: 'var(--dim3)',
        }}
      >
        LOT
      </label>
      <input
        id="jump-to-lot"
        data-testid="jump-input"
        value={jump}
        onChange={(e) => setJump(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== 'Enter') return;
          e.preventDefault();
          onJump(jump);
        }}
        placeholder="S-1200"
        aria-label="Jump to lot number"
        style={{
          width: 62,
          fontFamily: MONO,
          fontWeight: 500,
          fontSize: '11.5px',
          background: 'none',
          border: 'none',
          outline: 'none',
          color: 'var(--text)',
        }}
      />
    </div>
  );

  const search = (
    <div
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        height: mobile ? 36 : 34,
        padding: '0 6px 0 12px',
        borderRadius: 9,
        background: 'var(--s2)',
        border: '1px solid var(--line)',
        maxWidth: mobile ? undefined : 440,
        minWidth: 0,
      }}
    >
      <span style={{ fontFamily: MONO, fontSize: '12px', color: 'var(--dim3)' }}>⌕</span>
      <input
        ref={searchRef}
        type="search"
        data-testid="search-input"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder={mobile ? 'Search lots…' : 'Search lots…   ( / )'}
        style={{
          flex: 1,
          minWidth: 0,
          fontSize: mobile ? '13px' : '12.5px',
          background: 'none',
          border: 'none',
          outline: 'none',
          color: 'var(--text)',
        }}
      />
      <button
        type="button"
        data-testid="fuzzy-toggle"
        onClick={onFuzzyToggle}
        aria-pressed={fuzzy}
        aria-label="Toggle fuzzy search"
        title={fuzzy ? 'Fuzzy search on (tolerates typos)' : 'Exact search — toggle for fuzzy'}
        style={{
          flex: 'none',
          fontFamily: MONO,
          fontWeight: 500,
          fontSize: '9px',
          letterSpacing: '.1em',
          padding: '5px 7px',
          borderRadius: 6,
          background: fuzzy ? 'var(--lavbg)' : 'transparent',
          color: fuzzy ? 'var(--lavt)' : 'var(--dim3)',
        }}
      >
        {fuzzy ? 'FUZZY' : 'EXACT'}
      </button>
    </div>
  );

  const themeToggle = (
    <button
      type="button"
      onClick={onToggleTheme}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      style={{
        width: mobile ? 36 : 32,
        height: mobile ? 36 : 32,
        flex: 'none',
        borderRadius: 8,
        background: 'var(--s2)',
        border: '1px solid var(--line)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '13px',
        color: 'var(--dim2)',
      }}
    >
      {dark ? '☀' : '☾'}
    </button>
  );

  const tabs = (
    <nav style={{ display: 'flex', alignItems: 'center', gap: 2 }} aria-label="Lot view">
      {TABS.map((t) => {
        const on = tab === t.id;
        return (
          <button
            key={t.id}
            type="button"
            data-testid={t.testId}
            onClick={() => onTabChange(t.id)}
            aria-pressed={on}
            style={{
              padding: '7px 13px',
              borderRadius: 7,
              background: on ? 'var(--lavbg)' : 'transparent',
              fontWeight: on ? 600 : 500,
              fontSize: mobile ? '13px' : '12.5px',
              lineHeight: 1,
              color: on ? 'var(--lavt)' : 'var(--dim2)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              whiteSpace: 'nowrap',
            }}
          >
            {t.label}
            {t.id === 'watched' && (
              <span
                style={{
                  fontFamily: MONO,
                  fontWeight: 500,
                  fontSize: '9.5px',
                  lineHeight: 1,
                  padding: '3px 5px',
                  borderRadius: 4,
                  background: 'var(--s3)',
                  color: 'var(--dim2)',
                }}
              >
                {watchedCount}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );

  const count = (
    <p
      data-testid="result-count"
      style={{
        margin: 0,
        marginLeft: 'auto',
        flex: 'none',
        fontFamily: MONO,
        fontWeight: 500,
        fontSize: '10.5px',
        letterSpacing: '.08em',
        color: 'var(--dim3)',
        whiteSpace: 'nowrap',
      }}
    >
      {loading
        ? 'LOADING…'
        : `${filteredCount.toLocaleString('en-US')} / ${totalCount.toLocaleString('en-US')}${
            mobile ? '' : ' LOTS'
          }`}
    </p>
  );

  return (
    <header
      style={{
        flex: 'none',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--line)',
        position: 'relative',
        zIndex: 30,
      }}
    >
      {/* Row 1 — identity and search. */}
      {mobile ? (
        <div style={{ padding: '8px 12px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {search}
            <FiltersButton count={activeFilterCount} onClick={onOpenFilters} size={36} />
            {themeToggle}
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 0 2px',
              overflowX: 'auto',
            }}
            className="no-scrollbar"
          >
            {tabs}
            {count}
          </div>
        </div>
      ) : (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            height: 52,
            padding: '0 16px',
            borderBottom: '1px solid var(--line2)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 7, flex: 'none' }}>
            <span style={{ font: "400 19px/1 'Instrument Serif', serif" }}>Encore</span>
            <span
              style={{
                fontFamily: MONO,
                fontWeight: 500,
                fontSize: '8.5px',
                lineHeight: 1,
                letterSpacing: '.16em',
                color: 'var(--dim3)',
              }}
            >
              LOT BROWSER
            </span>
          </div>
          <div style={{ marginLeft: 8 }}>{tabs}</div>
          <div style={{ flex: 1, display: 'flex', marginLeft: 6, minWidth: 0 }}>{search}</div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              className="hint-keys"
              style={{
                fontFamily: MONO,
                fontWeight: 500,
                fontSize: '8.5px',
                letterSpacing: '.11em',
                color: 'var(--dim3)',
                whiteSpace: 'nowrap',
              }}
            >
              {coarse ? 'SWIPE → WATCH' : '← → MOVE · SPACE OPEN · W WATCH · / SEARCH'}
            </span>
            {jumpField}
            <div
              style={{
                display: 'flex',
                padding: 2,
                borderRadius: 8,
                background: 'var(--s2)',
                border: '1px solid var(--line)',
              }}
            >
              {(['grid', 'list'] as ViewMode[]).map((v) => {
                const on = view === v;
                return (
                  <button
                    key={v}
                    type="button"
                    data-testid={`view-${v}`}
                    onClick={() => onViewChange(v)}
                    aria-pressed={on}
                    style={{
                      padding: '5px 10px',
                      borderRadius: 6,
                      background: on ? 'var(--s3)' : 'transparent',
                      fontWeight: on ? 600 : 500,
                      fontSize: '11px',
                      lineHeight: 1,
                      color: on ? 'var(--text)' : 'var(--dim3)',
                      textTransform: 'capitalize',
                    }}
                  >
                    {v}
                  </button>
                );
              })}
            </div>
            {themeToggle}
          </div>
        </div>
      )}

      {/* Row 2 — the pinned rail. */}
      <div
        data-testid="header-rail"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          height: 44,
          padding: '0 16px',
          overflowX: 'auto',
        }}
        className="no-scrollbar"
      >
        <button
          type="button"
          data-testid="category-button"
          onClick={onOpenCategory}
          style={{
            ...railButton,
            background: categoryActive ? 'var(--lavbg)' : 'var(--s2)',
            borderColor: categoryActive ? 'var(--lavbd)' : 'var(--line)',
            color: categoryActive ? 'var(--lavt)' : 'var(--dim)',
          }}
        >
          <span
            style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {categoryLabel}
          </span>
          <span style={{ flex: 'none', color: 'var(--dim3)' }}>⌄</span>
        </button>

        <button
          type="button"
          data-testid="sort-button"
          onClick={onCycleSort}
          title="Cycle sort order"
          style={railButton}
        >
          <span style={{ color: 'var(--dim3)' }}>⇅</span>
          <span style={{ whiteSpace: 'nowrap' }}>{SORT_LABEL[sortKey]}</span>
        </button>

        <FiltersButton count={activeFilterCount} onClick={onOpenFilters} label="Filters" />

        {chips.length > 0 && (
          <span style={{ width: 1, height: 18, background: 'var(--line)', flex: 'none' }} />
        )}
        {chips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            data-testid={`chip-${chip.id}`}
            onClick={chip.onRemove}
            aria-label={`Remove filter: ${chip.label}`}
            style={{
              height: 26,
              padding: '0 8px',
              borderRadius: 20,
              background: 'var(--blushbg)',
              border: '1px solid var(--blushbd)',
              color: 'var(--blusht)',
              fontSize: '11px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              flex: 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {chip.label}
            <span style={{ opacity: 0.75 }}>✕</span>
          </button>
        ))}
        {chips.length > 0 && (
          <button
            type="button"
            data-testid="clear-filters-btn"
            onClick={onClearAll}
            style={{
              flex: 'none',
              fontFamily: MONO,
              fontWeight: 500,
              fontSize: '10.5px',
              letterSpacing: '.06em',
              color: 'var(--dim3)',
            }}
          >
            CLEAR
          </button>
        )}

        {!mobile && count}
      </div>
    </header>
  );
}

function FiltersButton({
  count,
  onClick,
  label,
  size,
}: {
  count: number;
  onClick: () => void;
  label?: string;
  size?: number;
}) {
  const on = count > 0;
  const badge: ReactNode = on && (
    <span
      style={{
        fontFamily: MONO,
        fontWeight: 700,
        fontSize: '9px',
        lineHeight: 1,
        padding: '2px 4px',
        borderRadius: 4,
        background: 'var(--lav)',
        color: 'var(--onlav)',
      }}
    >
      {count}
    </span>
  );

  if (size) {
    return (
      <button
        type="button"
        data-testid="filters-button"
        onClick={onClick}
        aria-label="Filters"
        style={{
          width: size,
          height: size,
          flex: 'none',
          borderRadius: 8,
          background: on ? 'var(--lavbg)' : 'var(--s2)',
          border: `1px solid ${on ? 'var(--lavbd)' : 'var(--line)'}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 4,
          fontSize: '13px',
          color: on ? 'var(--lavt)' : 'var(--dim2)',
          position: 'relative',
        }}
      >
        ⚙{badge}
      </button>
    );
  }

  return (
    <button
      type="button"
      data-testid="filters-button"
      onClick={onClick}
      style={{
        ...railButton,
        background: on ? 'var(--lavbg)' : 'var(--s2)',
        borderColor: on ? 'var(--lavbd)' : 'var(--line)',
        color: on ? 'var(--lavt)' : 'var(--dim)',
      }}
    >
      {label}
      {badge}
    </button>
  );
}
