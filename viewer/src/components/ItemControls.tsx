import { ChevronDown, ArrowDownUp } from 'lucide-react';
import type { Condition, SortKey } from '../lib/types';

interface Props {
  sortKey: SortKey;
  onSortChange: (s: SortKey) => void;
  /** Selected conditions (empty = no condition filter). */
  conditions: Set<Condition>;
  onToggleCondition: (c: Condition) => void;
  /** Condition values present in the data, in canonical order. */
  availableConditions: Condition[];
  /** 'sm' for the dense desktop bar, 'md' for the roomier mobile layout. */
  size?: 'sm' | 'md';
}

const SORT_OPTIONS: { id: SortKey; label: string }[] = [
  { id: 'lot', label: 'Lot number' },
  { id: 'resale-desc', label: 'Resale: high → low' },
  { id: 'resale-asc', label: 'Resale: low → high' },
  { id: 'retail-desc', label: 'Retail: high → low' },
];

/**
 * Sort + condition controls that narrow/order whatever lots are currently
 * shown (a Bat's List bucket, a category, search results, or a tab). Composes
 * with every other filter — it only reshapes the current view. First-class on
 * desktop and mobile: the chips wrap and the whole bar stacks at 'md'.
 */
export function ItemControls({
  sortKey,
  onSortChange,
  conditions,
  onToggleCondition,
  availableConditions,
  size = 'sm',
}: Props) {
  const h = size === 'sm' ? 'h-9' : 'h-10';

  return (
    <div
      data-testid="item-controls"
      className={`flex gap-x-3 gap-y-2 ${
        size === 'md' ? 'flex-col items-stretch' : 'flex-wrap items-center'
      }`}
    >
      <div className="flex items-center gap-2 shrink-0">
        <ArrowDownUp size={15} className="text-ink2 dark:text-bone2 shrink-0" />
        <div className="relative">
          <select
            data-testid="sort-select"
            aria-label="Sort lots"
            value={sortKey}
            onChange={(e) => onSortChange(e.target.value as SortKey)}
            className={`appearance-none ${h} pl-3.5 pr-9 ${
              size === 'md' ? 'w-full' : ''
            } rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-[13px] font-medium text-ink dark:text-bone focus:ring-2 focus:ring-ember focus:outline-none cursor-pointer`}
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown
            size={15}
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink2 dark:text-bone2"
          />
        </div>
      </div>

      {availableConditions.length > 0 && (
        <div
          data-testid="condition-filter"
          className="flex flex-wrap items-center gap-1.5"
        >
          {availableConditions.map((c) => {
            const active = conditions.has(c);
            return (
              <button
                key={c}
                type="button"
                data-testid={`condition-chip-${c}`}
                onClick={() => onToggleCondition(c)}
                aria-pressed={active}
                className={`inline-flex items-center ${h} px-3 text-[13px] font-medium rounded-full ring-1 transition-colors
                  ${
                    active
                      ? 'bg-ink text-paper ring-ink dark:bg-bone dark:text-night dark:ring-bone'
                      : 'bg-white dark:bg-night2 ring-rule dark:ring-dusk text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'
                  }`}
              >
                {c}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
