import { useEffect, type CSSProperties } from 'react';
import type { CatNode } from '../lib/categoryTree';
import { nodeAtPath } from '../lib/categoryTree';

/**
 * Category drill-down — docs/design/README.md § "Category drill-down".
 *
 * Two panes anchored under the rail: categories on the left with their lot
 * counts, sub-categories of the selection on the right. Picking a sub-category
 * closes the popover; "All categories" clears both. Replaces the cascading
 * <select> chain, which needed one interaction per level and gave no counts.
 *
 * The tree is deeper than two levels in places (20,122 lots sit at depth 3),
 * but the drill-down deliberately stops at sub-category: below that the counts
 * get too thin to be a useful way to navigate, and search covers it.
 */

interface Props {
  tree: CatNode;
  /** Selected prefix, root → leaf. Empty = "All categories". */
  selected: string[];
  onChange: (path: string[]) => void;
  onClose: () => void;
  sheet: boolean;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

/** Child names of the node at `path`, largest first, with counts. */
function childrenWithCounts(tree: CatNode, path: string[]): { name: string; count: number }[] {
  const node = nodeAtPath(tree, path);
  if (!node) return [];
  return Object.entries(node.children)
    .map(([name, child]) => ({ name, count: child.count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function CategoryPopover({ tree, selected, onChange, onClose, sheet }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const cats = childrenWithCounts(tree, []);
  const activeCat = selected[0] ?? null;
  const subs = activeCat ? childrenWithCounts(tree, [activeCat]) : [];

  const position: CSSProperties = sheet
    ? {
        left: 0,
        right: 0,
        bottom: 0,
        maxHeight: '80dvh',
        borderRadius: '18px 18px 0 0',
        animation: 'sheetup .18s ease-out',
      }
    : {
        left: 16,
        top: 104,
        borderRadius: 14,
        border: '1px solid var(--line)',
        animation: 'fadein .14s ease-out',
      };

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'var(--ov)',
          zIndex: 70,
          animation: 'fadein .14s ease-out',
        }}
      />
      <div
        data-testid="category-popover"
        role="dialog"
        aria-modal="true"
        aria-label="Categories"
        style={{
          position: 'fixed',
          zIndex: 71,
          background: 'var(--surface)',
          boxShadow: 'var(--sh)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          ...position,
        }}
      >
        <button
          type="button"
          data-testid="category-all"
          onClick={() => {
            onChange([]);
            onClose();
          }}
          style={{
            padding: '11px 14px',
            textAlign: 'left',
            borderBottom: '1px solid var(--line2)',
            fontSize: '12.5px',
            fontWeight: 500,
            color: selected.length === 0 ? 'var(--lavt)' : 'var(--dim)',
          }}
        >
          All categories
        </button>

        <div style={{ display: 'flex', minHeight: 0 }}>
          <Pane
            testId="category-level-0"
            items={cats}
            activeName={activeCat}
            sheet={sheet}
            onPick={(name) => onChange([name])}
          />
          <div style={{ width: 1, background: 'var(--line2)', flex: 'none' }} />
          <Pane
            testId="category-level-1"
            items={subs}
            activeName={selected[1] ?? null}
            sheet={sheet}
            empty={activeCat ? 'No sub-categories' : 'Pick a category'}
            onPick={(name) => {
              onChange([activeCat!, name]);
              onClose();
            }}
          />
        </div>
      </div>
    </>
  );
}

function Pane({
  items,
  activeName,
  onPick,
  testId,
  empty,
  sheet,
}: {
  items: { name: string; count: number }[];
  activeName: string | null;
  onPick: (name: string) => void;
  testId: string;
  empty?: string;
  sheet: boolean;
}) {
  return (
    <div
      data-testid={testId}
      style={{
        width: sheet ? '50%' : 210,
        flex: sheet ? '1 1 0' : 'none',
        maxHeight: sheet ? '60dvh' : '60vh',
        overflowY: 'auto',
        padding: '6px 0',
      }}
    >
      {items.length === 0 && empty && (
        <div
          style={{
            padding: '12px 14px',
            fontFamily: MONO,
            fontSize: '9px',
            letterSpacing: '.1em',
            color: 'var(--dim3)',
          }}
        >
          {empty.toUpperCase()}
        </div>
      )}
      {items.map((item) => {
        const on = item.name === activeName;
        return (
          <button
            key={item.name}
            type="button"
            onClick={() => onPick(item.name)}
            aria-pressed={on}
            style={{
              width: '100%',
              minHeight: sheet ? 44 : 32,
              padding: '7px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              textAlign: 'left',
              background: on ? 'var(--lavbg)' : 'transparent',
              color: on ? 'var(--lavt)' : 'var(--dim)',
              fontSize: '12px',
              fontWeight: on ? 600 : 400,
            }}
          >
            <span
              style={{
                flex: 1,
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {item.name}
            </span>
            <span
              style={{
                flex: 'none',
                fontFamily: MONO,
                fontSize: '9.5px',
                color: 'var(--dim3)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {item.count.toLocaleString('en-US')}
            </span>
          </button>
        );
      })}
    </div>
  );
}
