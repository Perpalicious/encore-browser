import { useEffect, type CSSProperties } from 'react';

/**
 * The two-pane drill-down — docs/design/README.md § "Category drill-down".
 *
 * Anchored under the rail on desktop, a bottom sheet under a coarse pointer.
 * Left pane picks a parent and stays open; right pane picks a child and closes.
 * Both panes show counts, which is the whole reason the level exists — you can
 * see how much is behind a choice before committing to it.
 *
 * Two things use this shape: categories → sub-categories, and Bat's List
 * groups → buckets. They are the same interaction over different trees, so
 * they share the shell and differ only in what they are fed and what their
 * test ids are called.
 */

export interface DrillItem {
  name: string;
  count: number;
}

export interface DrillPane {
  testId: string;
  items: DrillItem[];
  /** Highlighted item, if any. */
  activeName: string | null;
  /** Shown when `items` is empty. */
  empty?: string;
  onPick: (name: string) => void;
}

interface Props {
  testId: string;
  ariaLabel: string;
  /** The full-width header button — the "everything" escape hatch. */
  clearLabel: string;
  clearActive: boolean;
  onClear: () => void;
  clearTestId: string;
  left: DrillPane;
  right: DrillPane;
  /** Bottom sheet instead of an anchored popover. */
  sheet: boolean;
  onClose: () => void;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

export function DrillPopover({
  testId,
  ariaLabel,
  clearLabel,
  clearActive,
  onClear,
  clearTestId,
  left,
  right,
  sheet,
  onClose,
}: Props) {
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
        data-testid={testId}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
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
          data-testid={clearTestId}
          onClick={() => {
            onClear();
            onClose();
          }}
          style={{
            padding: '11px 14px',
            textAlign: 'left',
            borderBottom: '1px solid var(--line2)',
            fontSize: '12.5px',
            fontWeight: 500,
            color: clearActive ? 'var(--lavt)' : 'var(--dim)',
          }}
        >
          {clearLabel}
        </button>

        <div style={{ display: 'flex', minHeight: 0 }}>
          <Pane {...left} sheet={sheet} />
          <div style={{ width: 1, background: 'var(--line2)', flex: 'none' }} />
          <Pane {...right} sheet={sheet} />
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
}: DrillPane & { sheet: boolean }) {
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
            data-testid={`${testId}-${item.name}`}
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
