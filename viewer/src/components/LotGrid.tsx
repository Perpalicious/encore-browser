import { useMemo, useRef } from 'react';
import { useWindowVirtualizer } from '@tanstack/react-virtual';
import type { Lot, Density, Tab } from '../lib/types';
import { LotCard } from './LotCard';
import { LotExpandPanel } from './LotExpandPanel';
import { SkeletonCard } from './SkeletonCard';
import { EmptyState } from './EmptyState';
import { useColumns } from '../hooks/useColumns';

// A grid row is either:
// - 'cards': an array of Lots for that row
// - 'panel': a single expanded lot to show as full-row panel (compact mode)
type GridRow =
  | { type: 'cards'; lots: Lot[] }
  | { type: 'panel'; lot: Lot };

interface Props {
  lots: Lot[];
  loading: boolean;
  density: Density;
  tab: Tab;
  expandedIds: Set<string>;
  watched: Set<string>;
  onToggleExpand: (lotNumber: string) => void;
  onToggleWatch: (lotNumber: string) => void;
  onClearFilters: () => void;
}

// Estimate row heights for the virtualizer (rough, will be measured)
function estimateRowHeight(row: GridRow, density: Density): number {
  if (row.type === 'panel') {
    return 480;
  }
  // card row: image + body
  const compact = density === 'compact';
  return compact ? 280 : 340;
}

export function LotGrid({
  lots,
  loading,
  density,
  tab,
  expandedIds,
  watched,
  onToggleExpand,
  onToggleWatch,
  onClearFilters,
}: Props) {
  const columns = useColumns(density);
  const compact = density === 'compact';
  const listRef = useRef<HTMLDivElement>(null);

  // Build grid rows: chunk lots into rows of `columns`, then insert panel rows
  // after each row that contains an expanded card (compact mode only)
  const rows = useMemo<GridRow[]>(() => {
    const result: GridRow[] = [];
    for (let i = 0; i < lots.length; i += columns) {
      const rowLots = lots.slice(i, i + columns);
      result.push({ type: 'cards', lots: rowLots });
      // In compact mode, insert full-row expand panels after this row
      if (compact) {
        for (const lot of rowLots) {
          if (expandedIds.has(lot.lot_number)) {
            result.push({ type: 'panel', lot });
          }
        }
      }
    }
    return result;
  }, [lots, columns, compact, expandedIds]);

  const rowVirtualizer = useWindowVirtualizer({
    count: rows.length,
    estimateSize: (i) => estimateRowHeight(rows[i], density),
    overscan: 5,
    scrollMargin: listRef.current?.offsetTop ?? 0,
  });

  const gridClass = compact
    ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'
    : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4';

  if (loading) {
    return (
      <div className={`grid gap-4 md:gap-5 ${gridClass}`}>
        {Array.from({ length: 8 }).map((_, i) => (
          <SkeletonCard key={i} density={density} />
        ))}
      </div>
    );
  }

  if (lots.length === 0) {
    return <EmptyState tab={tab} onClear={onClearFilters} />;
  }

  return (
    <>
      <div
        ref={listRef}
        style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const row = rows[virtualRow.index];
          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start - rowVirtualizer.options.scrollMargin}px)`,
              }}
            >
              {row.type === 'cards' ? (
                <div className={`grid gap-4 md:gap-5 ${gridClass} pb-4 md:pb-5`}>
                  {row.lots.map((lot) => (
                    <LotCard
                      key={lot.lot_number}
                      lot={lot}
                      expanded={expandedIds.has(lot.lot_number)}
                      onToggleExpand={() => onToggleExpand(lot.lot_number)}
                      watched={watched.has(lot.lot_number)}
                      onToggleWatch={() => onToggleWatch(lot.lot_number)}
                      density={density}
                      inlineExpand={!compact}
                    />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-1 pb-4 md:pb-5">
                  <LotExpandPanel
                    lot={row.lot}
                    fullRow
                    onCollapse={() => onToggleExpand(row.lot.lot_number)}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-12 text-center text-[11px] font-mono uppercase tracking-[0.18em] text-ink2/60 dark:text-bone2/60">
        End of lots · {lots.length} shown
      </p>
    </>
  );
}
