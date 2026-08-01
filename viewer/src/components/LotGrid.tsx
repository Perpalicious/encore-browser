import {
  useRef,
  useState,
  useEffect,
  useImperativeHandle,
  forwardRef,
  type UIEvent,
} from 'react';
import type { Lot, Density, Tab, MobileCols, MobileView, ViewMode } from '../lib/types';
import type { LotView } from '../lib/lotView';
import { LotCard } from './LotCard';
import { LotRow } from './LotRow';
import { EmptyState } from './EmptyState';
import { useGridGeometry, textBlockHeight } from '../hooks/useGridGeometry';

/**
 * The virtualised lot list — docs/design/README.md § "Virtualisation".
 *
 * Row heights are UNIFORM, which is what makes this cheap: a spacer div of
 * `totalRows * rowH` establishes the scrollbar, and the visible window is one
 * absolutely-positioned block at `top: first * rowH`. Nothing is measured after
 * paint, and the grid never reflows — expanding a lot opens an overlay rather
 * than inserting anything into the flow.
 *
 * That uniformity is a real constraint, not an implementation detail. The card
 * clamps its title to two lines and pins its text block to a fixed height for
 * exactly this reason: if cards could vary in height, the spacer and the
 * window's offset — both derived from rowH — would drift out of sync with the
 * scrollbar. If a third title line is ever needed, make EVERY card taller
 * (raise the title height and TEXT_H together) rather than letting heights
 * vary; genuinely variable heights need measured virtualisation.
 */

interface Props {
  lots: Lot[];
  /** lot_number → presentation record (see lib/lotView.ts). */
  viewByLot: Map<string, LotView>;
  loading: boolean;
  density: Density;
  tab: Tab;
  view: ViewMode;
  mobile: boolean;
  coarse: boolean;
  mobileView: MobileView;
  mobileCols: MobileCols;
  onMobileViewChange: (v: MobileView) => void;
  onMobileColsChange: (c: MobileCols) => void;
  /** Index into `lots` of the keyboard cursor, or -1. */
  cursor: number;
  onCursorChange: (i: number) => void;
  expandedId: string | null;
  watched: Set<string>;
  onToggleExpand: (lotNumber: string) => void;
  onToggleWatch: (lotNumber: string) => void;
  onClearFilters: () => void;
  /** True when a single day is filtered — the day label is then redundant. */
  singleDay: boolean;
  /** Scroll offset to restore once the skeletons clear. */
  initialScrollTop?: number;
  onScrollTopChange?: (value: number) => void;
}

/** Imperative handle so keyboard navigation can drive the scroll container. */
export interface LotGridHandle {
  /** Columns currently laid out — the ↑/↓ step size. */
  cols: number;
  /**
   * Scroll the given index into view by direct arithmetic, not scrollIntoView.
   * `'nearest'` (the default) moves as little as possible, which is what
   * arrow-key stepping wants; `'top'` parks the row at the top of the
   * viewport, which is what a jump from somewhere else entirely wants.
   */
  revealIndex: (index: number, align?: 'nearest' | 'top') => void;
}

/** Rows rendered above and below the viewport. */
const OVERSCAN = 2;
/** Ignore scroll deltas smaller than this — sub-pixel jitter costs renders. */
const SCROLL_EPSILON = 4;
const MAX_SKELETONS = 36;
/**
 * Height of the sticky group bar. Fixed rather than measured so the grid's
 * offset inside the scroller is a known constant — the window math subtracts it
 * from scrollTop, and measuring it would make that a frame-late guess.
 */
const GROUP_BAR_H = 28;
const MONO = "'JetBrains Mono', ui-monospace, monospace";

export const LotGrid = forwardRef<LotGridHandle, Props>(function LotGrid(
  {
    lots,
    viewByLot,
    loading,
    density,
    tab,
    view,
    mobile,
    coarse,
    mobileView,
    mobileCols,
    onMobileViewChange,
    onMobileColsChange,
    cursor,
    onCursorChange,
    expandedId,
    watched,
    onToggleExpand,
    onToggleWatch,
    onClearFilters,
    singleDay,
    initialScrollTop = 0,
    onScrollTopChange,
  },
  ref
) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const rowsMode = mobile ? mobileView === 'rows' : view === 'list';
  const geo = useGridGeometry(scrollRef, {
    density,
    mobile,
    coarse,
    rows: rowsMode,
    mobileCols,
  });
  const { mode, cols, colW, rowH, gap, padX, vh } = geo;

  const totalRows = Math.ceil(lots.length / cols);
  const totalH = totalRows * rowH;

  const showGroupBar = !loading && lots.length > 0;
  // Everything above the grid inside the scroller. scrollTop is measured from
  // the top of the scroller, the grid's rows from the top of the spacer.
  const contentTop = (showGroupBar ? GROUP_BAR_H : 0) + (mode === 'card' ? gap : 0);

  const onScroll = (e: UIEvent<HTMLDivElement>) => {
    const next = e.currentTarget.scrollTop;
    setScrollTop((prev) => (Math.abs(next - prev) > SCROLL_EPSILON ? next : prev));
    onScrollTopChange?.(next);
  };

  // Restore the previous scroll position one frame after the skeletons clear —
  // any earlier and the spacer that gives the container its height doesn't
  // exist yet, so the browser clamps the assignment straight back to 0.
  const restored = useRef(false);
  useEffect(() => {
    if (loading || restored.current || initialScrollTop <= 0 || lots.length === 0) return;
    restored.current = true;
    const id = requestAnimationFrame(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = initialScrollTop;
        setScrollTop(initialScrollTop);
      }
    });
    return () => cancelAnimationFrame(id);
  }, [loading, initialScrollTop, lots.length]);

  useImperativeHandle(
    ref,
    () => ({
      cols,
      revealIndex(index: number, align: 'nearest' | 'top' = 'nearest') {
        const el = scrollRef.current;
        if (!el || index < 0) return;
        const rowTop = Math.floor(index / cols) * rowH + contentTop;
        const rowBottom = rowTop + rowH;
        // Direct scrollTop arithmetic, not scrollIntoView: the window is
        // absolutely positioned, so scrollIntoView would fight the virtualiser.
        if (align === 'top') el.scrollTop = rowTop;
        else if (rowTop < el.scrollTop) el.scrollTop = rowTop;
        else if (rowBottom > el.scrollTop + vh) el.scrollTop = rowBottom - vh;
        setScrollTop(el.scrollTop);
      },
    }),
    [cols, rowH, vh, contentTop]
  );

  // Clamp against the current content: filters can shrink the list under a
  // scroll position that was valid a moment ago. The browser will correct the
  // element and fire a scroll event, but this keeps that frame from blanking.
  const top = Math.max(0, Math.min(scrollTop - contentTop, Math.max(0, totalH - vh)));
  const first = Math.max(0, Math.floor(top / rowH) - OVERSCAN);
  const last = Math.min(totalRows, Math.ceil((top + vh) / rowH) + OVERSCAN);
  const visible = lots.slice(first * cols, last * cols);

  // The group bar reads off the window, so it updates as you scroll.
  const firstVisible = visible.length > 0 ? viewByLot.get(visible[0].lot_number) : undefined;
  const lastVisible =
    visible.length > 0 ? viewByLot.get(visible[visible.length - 1].lot_number) : undefined;

  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
    gap: `${gap}px`,
    padding: `0 ${padX}px`,
  } as const;

  let body;
  if (loading) {
    // Skeletons shaped to the CURRENT view — a user who works in List must not
    // be shown card skeletons, that reads as a broken page. Enough to fill
    // exactly one screen rather than a fixed count.
    const perScreen = Math.ceil(vh / rowH) + 1;
    const count = Math.min(MAX_SKELETONS, mode === 'card' ? cols * perScreen : perScreen) || cols;
    body =
      mode === 'card' ? (
        <div style={{ ...gridStyle, paddingTop: gap }}>
          {Array.from({ length: count }).map((_, i) => (
            <SkeletonCard key={i} delay={(i % 6) * 90} />
          ))}
        </div>
      ) : (
        <div>
          {Array.from({ length: count }).map((_, i) => (
            <SkeletonRow key={i} delay={(i % 6) * 90} height={rowH} thumb={mobile ? 58 : 52} />
          ))}
        </div>
      );
  } else if (lots.length === 0) {
    body = <EmptyState tab={tab} onClear={onClearFilters} />;
  } else {
    body = (
      <>
        <div style={{ position: 'relative', height: totalH, width: '100%' }}>
          <div
            style={
              mode === 'card'
                ? { ...gridStyle, position: 'absolute', left: 0, right: 0, top: first * rowH }
                : { position: 'absolute', left: 0, right: 0, top: first * rowH }
            }
          >
            {visible.map((lot, i) => {
              const v = viewByLot.get(lot.lot_number);
              if (!v) return null;
              const index = first * cols + i;
              const isCursor = index === cursor;
              const open = () => {
                onCursorChange(index);
                onToggleExpand(lot.lot_number);
              };
              return mode === 'card' ? (
                <LotCard
                  key={lot.lot_number}
                  view={v}
                  colW={colW}
                  mobileCols={mobile ? mobileCols : undefined}
                  textH={textBlockHeight(mobile, mobileCols)}
                  expanded={lot.lot_number === expandedId}
                  cursor={isCursor}
                  onToggleExpand={open}
                  watched={watched.has(lot.lot_number)}
                  onToggleWatch={() => onToggleWatch(lot.lot_number)}
                />
              ) : (
                <LotRow
                  key={lot.lot_number}
                  view={v}
                  mobile={mobile}
                  coarse={coarse}
                  height={rowH}
                  watched={watched.has(lot.lot_number)}
                  cursor={isCursor || lot.lot_number === expandedId}
                  onOpen={open}
                  onToggleWatch={() => onToggleWatch(lot.lot_number)}
                />
              );
            })}
          </div>
        </div>
        <p
          style={{
            margin: '24px 0 32px',
            textAlign: 'center',
            fontFamily: MONO,
            fontWeight: 500,
            fontSize: '10.5px',
            letterSpacing: '.08em',
            textTransform: 'uppercase',
            color: 'var(--dim3)',
          }}
        >
          End of lots · {lots.length} shown
        </p>
      </>
    );
  }

  const groupBar = showGroupBar && firstVisible && lastVisible && (
    <div
      data-testid="group-bar"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        height: GROUP_BAR_H,
        boxSizing: 'border-box',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '0 14px',
        background: 'var(--bg)',
        borderBottom: '1px solid var(--line2)',
        fontFamily: MONO,
        fontWeight: 500,
        fontSize: '9.5px',
        letterSpacing: '.1em',
        color: 'var(--dim3)',
      }}
    >
      {/* The day is redundant once a single day is filtered. */}
      {!singleDay && (
        <span style={{ color: 'var(--dim2)' }}>
          {firstVisible.day === 'M' ? 'MONDAY' : 'SUNDAY'}
        </span>
      )}
      {!singleDay && <span>·</span>}
      <span>
        {firstVisible.lot} → {lastVisible.lot}
      </span>

      {/* On mobile the bar also carries the layout controls. */}
      {mobile && (
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Segments
            testIdPrefix="mview"
            options={[
              { id: 'rows', label: 'Rows' },
              { id: 'cards', label: 'Cards' },
            ]}
            value={mobileView}
            onChange={(v) => onMobileViewChange(v as MobileView)}
          />
          {mobileView === 'cards' && (
            <Segments
              testIdPrefix="cols"
              width={22}
              options={[
                { id: '2', label: '2' },
                { id: '3', label: '3' },
                { id: '4', label: '4' },
              ]}
              value={String(mobileCols)}
              onChange={(v) => onMobileColsChange(Number(v) as MobileCols)}
            />
          )}
        </div>
      )}
    </div>
  );

  return (
    <div
      ref={scrollRef}
      onScroll={onScroll}
      data-testid="lot-scroller"
      style={{
        flex: '1 1 auto',
        minHeight: 0,
        overflowY: 'auto',
        overflowX: 'hidden',
        position: 'relative',
        background: 'var(--bg)',
      }}
    >
      {groupBar}
      <div style={{ paddingTop: mode === 'card' ? gap : 0 }}>{body}</div>
    </div>
  );
});

function Segments({
  options,
  value,
  onChange,
  testIdPrefix,
  width,
}: {
  options: { id: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  testIdPrefix: string;
  width?: number;
}) {
  return (
    <div style={{ display: 'flex', padding: 2, borderRadius: 7, background: 'var(--s2)' }}>
      {options.map((o) => {
        const on = value === o.id;
        return (
          <button
            key={o.id}
            type="button"
            data-testid={`${testIdPrefix}-${o.id}`}
            onClick={() => onChange(o.id)}
            aria-pressed={on}
            style={{
              width,
              padding: width ? '3px 0' : '3px 8px',
              borderRadius: 5,
              background: on ? 'var(--s3)' : 'transparent',
              fontFamily: MONO,
              fontWeight: on ? 600 : 500,
              fontSize: '9.5px',
              letterSpacing: '.06em',
              color: on ? 'var(--text)' : 'var(--dim3)',
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Card-shaped loading placeholder: square tile plus two text bars. */
function SkeletonCard({ delay }: { delay: number }) {
  return (
    <div
      style={{
        borderRadius: 11,
        background: 'var(--surface)',
        border: '1px solid var(--line2)',
        overflow: 'hidden',
        animation: 'sk 1.4s ease-in-out infinite',
        animationDelay: `${delay}ms`,
      }}
    >
      <div style={{ aspectRatio: '1 / 1', background: 'var(--sk)' }} />
      <div style={{ padding: 9, display: 'flex', flexDirection: 'column', gap: 7 }}>
        <div style={{ height: 9, borderRadius: 4, background: 'var(--sk2)' }} />
        <div style={{ height: 9, width: '62%', borderRadius: 4, background: 'var(--sk)' }} />
      </div>
    </div>
  );
}

/** Row-shaped loading placeholder, for list and mobile-rows modes. */
function SkeletonRow({ delay, height, thumb }: { delay: number; height: number; thumb: number }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '0 13px',
        height,
        borderBottom: '1px solid var(--line2)',
        animation: 'sk 1.4s ease-in-out infinite',
        animationDelay: `${delay}ms`,
      }}
    >
      <div
        style={{
          width: thumb,
          height: thumb,
          borderRadius: 9,
          background: 'var(--sk)',
          flex: 'none',
        }}
      />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 7 }}>
        <div style={{ height: 9, borderRadius: 4, background: 'var(--sk2)' }} />
        <div style={{ height: 9, width: '46%', borderRadius: 4, background: 'var(--sk)' }} />
      </div>
      <div
        style={{ width: 58, height: 11, borderRadius: 4, background: 'var(--sk2)', flex: 'none' }}
      />
    </div>
  );
}
