import type { CSSProperties } from 'react';
import type { LegendGroup } from '../lib/legend';

/**
 * The recall legend: a reminder of the searches we usually run, tucked behind
 * one small rail button. Open, it is a strip under the rail — group names and
 * term chips — and a click on a term fills the search box. It changes nothing
 * else: no filter reads it, and the grid below keeps its own scroll.
 */

const MONO = "'JetBrains Mono', ui-monospace, monospace";

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
};

export function LegendButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      data-testid="legend-button"
      onClick={onToggle}
      aria-expanded={open}
      aria-controls="legend-strip"
      title="Searches we usually run"
      style={{
        ...railButton,
        background: open ? 'var(--lavbg)' : 'var(--s2)',
        borderColor: open ? 'var(--lavbd)' : 'var(--line)',
        color: open ? 'var(--lavt)' : 'var(--dim)',
      }}
    >
      <span style={{ fontFamily: MONO, fontSize: '9.5px', letterSpacing: '.12em' }}>LEGEND</span>
      <span aria-hidden style={{ fontSize: '10px', color: 'var(--dim3)' }}>{open ? '⌃' : '⌄'}</span>
    </button>
  );
}

export function LegendStrip({
  groups,
  onPick,
  onClose,
}: {
  groups: LegendGroup[];
  onPick: (term: string) => void;
  onClose: () => void;
}) {
  if (groups.length === 0) return null;
  return (
    <div
      id="legend-strip"
      data-testid="legend-strip"
      style={{
        flex: 'none',
        maxHeight: '30dvh',
        overflowY: 'auto',
        borderBottom: '1px solid var(--line)',
        background: 'var(--surface)',
        padding: '6px 16px 8px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
      }}
    >
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {groups.map((g) => (
          <div
            key={g.name}
            data-testid="legend-group"
            style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}
          >
            <span
              style={{
                fontFamily: MONO,
                fontWeight: 500,
                fontSize: '8.5px',
                letterSpacing: '.13em',
                color: 'var(--dim3)',
                textTransform: 'uppercase',
                flex: 'none',
                minWidth: 96,
              }}
            >
              {g.name}
            </span>
            <span style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {g.terms.map((term) => (
                <button
                  key={term}
                  type="button"
                  data-testid="legend-term"
                  onClick={() => onPick(term)}
                  title={`Search “${term}”`}
                  style={{
                    height: 24,
                    padding: '0 8px',
                    borderRadius: 7,
                    background: 'var(--s2)',
                    border: '1px solid var(--line)',
                    fontSize: '11px',
                    fontWeight: 500,
                    color: 'var(--dim)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {term}
                </button>
              ))}
            </span>
          </div>
        ))}
      </div>
      <button
        type="button"
        data-testid="legend-close"
        aria-label="Hide legend"
        onClick={onClose}
        style={{
          flex: 'none',
          width: 26,
          height: 26,
          borderRadius: 7,
          background: 'transparent',
          border: '1px solid var(--line)',
          color: 'var(--dim2)',
          fontSize: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'sticky',
          top: 0,
        }}
      >
        ✕
      </button>
    </div>
  );
}
