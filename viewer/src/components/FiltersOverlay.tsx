import { useEffect, type CSSProperties, type ReactNode } from 'react';
import type {
  Condition,
  ConfidenceFilter,
  DayFilter,
  Density,
  OutlookFilter,
  SortKey,
} from '../lib/types';
import { OUTLOOK_ORDER } from '../lib/types';

/**
 * The filters overlay — docs/design/README.md § "Filters overlay".
 *
 * Everything in the old header that was a CONTROL now lives behind this one
 * button; everything that was STATE surfaces as a removable chip on the rail.
 * Nothing is hidden — you can always see what you filtered.
 *
 * Desktop: an anchored popover under the rail. Touch: a bottom sheet, with
 * every target at least 44px so it works one-handed.
 */

interface Props {
  sheet: boolean;
  resultCount: number;
  availableConditions: Condition[];
  conditions: Set<Condition>;
  onToggleCondition: (c: Condition) => void;
  confidenceFilter: ConfidenceFilter;
  onConfidenceChange: (c: ConfidenceFilter) => void;
  outlookFilter: OutlookFilter;
  onOutlookChange: (o: OutlookFilter) => void;
  dayFilter: DayFilter;
  onDayChange: (d: DayFilter) => void;
  sortKey: SortKey;
  onSortChange: (s: SortKey) => void;
  density: Density;
  onDensityChange: (d: Density) => void;
  personalOnly: boolean;
  onPersonalToggle: () => void;
  potentialOnly: boolean;
  onPotentialToggle: () => void;
  onClearAll: () => void;
  onClose: () => void;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

const CONFIDENCE_OPTIONS: { id: ConfidenceFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'medium-plus', label: 'Med+' },
  { id: 'high', label: 'High' },
];

const DAY_OPTIONS: { id: DayFilter; label: string }[] = [
  { id: 'Sunday', label: 'Sun' },
  { id: 'Monday', label: 'Mon' },
  { id: 'Both', label: 'Both' },
];

const DENSITY_OPTIONS: { id: Density; label: string }[] = [
  { id: 'standard', label: 'Standard' },
  { id: 'compact', label: 'Compact' },
];

const SORT_OPTIONS: { id: SortKey; label: string }[] = [
  { id: 'lot', label: 'Lot number' },
  { id: 'resale-desc', label: 'Resale high → low' },
  { id: 'resale-asc', label: 'Resale low → high' },
  { id: 'retail-desc', label: 'Retail high → low' },
];

export function FiltersOverlay({
  sheet,
  resultCount,
  availableConditions,
  conditions,
  onToggleCondition,
  confidenceFilter,
  onConfidenceChange,
  outlookFilter,
  onOutlookChange,
  dayFilter,
  onDayChange,
  sortKey,
  onSortChange,
  density,
  onDensityChange,
  personalOnly,
  onPersonalToggle,
  potentialOnly,
  onPotentialToggle,
  onClearAll,
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
        maxHeight: '86dvh',
        borderRadius: '18px 18px 0 0',
        animation: 'sheetup .18s ease-out',
      }
    : {
        top: 100,
        right: 16,
        width: 420,
        maxHeight: '78dvh',
        border: '1px solid var(--line)',
        borderRadius: 14,
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
        data-testid="filters-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="Filters"
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
        <div
          style={{
            padding: '14px 16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 15,
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ fontWeight: 600, fontSize: '15px' }}>Filters</span>
            <button
              type="button"
              data-testid="filters-clear"
              onClick={onClearAll}
              style={{
                marginLeft: 'auto',
                fontFamily: MONO,
                fontWeight: 500,
                fontSize: '11px',
                color: 'var(--lavt)',
              }}
            >
              CLEAR
            </button>
          </div>

          <Section label="CONDITION">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {availableConditions.map((c) => (
                <Chip
                  key={c}
                  testId={`condition-chip-${c}`}
                  label={c}
                  selected={conditions.has(c)}
                  onClick={() => onToggleCondition(c)}
                />
              ))}
            </div>
          </Section>

          <Section label="RESALE CONFIDENCE">
            <Segmented
              options={CONFIDENCE_OPTIONS}
              value={confidenceFilter}
              onChange={onConfidenceChange}
              testIdPrefix="confidence"
            />
          </Section>

          <Section label="OUTLOOK">
            {/* Three steps, not the handoff's four — our resale pass never
                emits a 'Strong' above 'Good'. */}
            <Segmented
              options={[
                { id: 'all' as OutlookFilter, label: 'All' },
                ...OUTLOOK_ORDER.map((o) => ({
                  id: o as OutlookFilter,
                  label: o.charAt(0).toUpperCase() + o.slice(1),
                })),
              ]}
              value={outlookFilter}
              onChange={onOutlookChange}
              testIdPrefix="outlook"
            />
          </Section>

          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Section label="DAY">
                <Segmented
                  options={DAY_OPTIONS}
                  value={dayFilter}
                  onChange={onDayChange}
                  testIdPrefix="day"
                />
              </Section>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Section label="SORT">
                <select
                  data-testid="sort-select"
                  value={sortKey}
                  onChange={(e) => onSortChange(e.target.value as SortKey)}
                  style={{
                    width: '100%',
                    height: 44,
                    padding: '0 10px',
                    borderRadius: 9,
                    background: 'var(--s2)',
                    border: '1px solid var(--line)',
                    color: 'var(--text)',
                    fontSize: '12.5px',
                    fontWeight: 500,
                  }}
                >
                  {SORT_OPTIONS.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Section>
            </div>
          </div>

          <Section label="DENSITY">
            {/* No desktop density in the handoff — columns are computed — but
                this app has always had the control, and it still means
                something: it picks both the target column width the grid packs
                to and the column ceiling (6 standard, 8 compact). */}
            <Segmented
              options={DENSITY_OPTIONS}
              value={density}
              onChange={onDensityChange}
              testIdPrefix="density"
            />
          </Section>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            <Toggle
              testId="personal-picks-toggle"
              label="♥ Personal picks"
              on={personalOnly}
              onClick={onPersonalToggle}
            />
            <Toggle
              testId="potential-resales-toggle"
              label="↗ Potential resales"
              on={potentialOnly}
              onClick={onPotentialToggle}
            />
          </div>

          <button
            type="button"
            data-testid="filters-apply"
            onClick={onClose}
            style={{
              height: 44,
              borderRadius: 9,
              background: 'var(--lav)',
              color: 'var(--onlav)',
              fontSize: '12.5px',
              fontWeight: 600,
            }}
          >
            Show {resultCount.toLocaleString('en-US')} lot{resultCount === 1 ? '' : 's'}
          </button>
        </div>
      </div>
    </>
  );
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontFamily: MONO,
          fontWeight: 500,
          fontSize: '8.5px',
          letterSpacing: '.13em',
          color: 'var(--dim3)',
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}

function Chip({
  label,
  selected,
  onClick,
  testId,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  testId: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      aria-pressed={selected}
      style={{
        minHeight: 44,
        padding: '9px 13px',
        borderRadius: 9,
        background: selected ? 'var(--lavbg)' : 'var(--s2)',
        border: `1px solid ${selected ? 'var(--lavbd)' : 'var(--line)'}`,
        fontSize: '12.5px',
        fontWeight: 500,
        color: selected ? 'var(--lavt)' : 'var(--dim)',
      }}
    >
      {label}
    </button>
  );
}

function Segmented<T extends string>({
  options,
  value,
  onChange,
  testIdPrefix,
}: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  testIdPrefix: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 4,
        padding: 3,
        borderRadius: 10,
        background: 'var(--s2)',
      }}
    >
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
              flex: 1,
              minWidth: 0,
              height: 38,
              borderRadius: 8,
              background: on ? 'var(--s3)' : 'transparent',
              fontSize: '12.5px',
              fontWeight: on ? 600 : 500,
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

function Toggle({
  label,
  on,
  onClick,
  testId,
}: {
  label: string;
  on: boolean;
  onClick: () => void;
  testId: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      aria-pressed={on}
      style={{
        minHeight: 44,
        padding: '9px 13px',
        borderRadius: 9,
        background: on ? 'var(--blushbg)' : 'var(--s2)',
        border: `1px solid ${on ? 'var(--blushbd)' : 'var(--line)'}`,
        fontSize: '12.5px',
        fontWeight: 500,
        color: on ? 'var(--blusht)' : 'var(--dim)',
      }}
    >
      {label}
    </button>
  );
}
