import { TrendingUp } from 'lucide-react';
import type { ConfidenceFilter } from '../lib/types';

interface Props {
  confidenceFilter: ConfidenceFilter;
  onConfidenceChange: (c: ConfidenceFilter) => void;
  potentialOnly: boolean;
  onPotentialToggle: () => void;
  /** 'sm' for the dense desktop header, 'md' for the mobile filter panel. */
  size?: 'sm' | 'md';
}

const CONFIDENCE_OPTIONS: { id: ConfidenceFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'medium-plus', label: 'Med+' },
  { id: 'high', label: 'High' },
];

/**
 * The two resale filters: a "Potential resales" toggle (demand-aware: good/fair
 * outlook AND medium/high confidence) and a resale-confidence segmented filter
 * (All / Med+ / High). Both narrow within the current tab/category/search view.
 */
export function ResaleFilter({
  confidenceFilter,
  onConfidenceChange,
  potentialOnly,
  onPotentialToggle,
  size = 'sm',
}: Props) {
  const h = size === 'sm' ? 'h-[34px]' : 'h-9';
  const text = size === 'sm' ? 'text-[13px]' : 'text-[13px]';

  return (
    <div
      data-testid="resale-filter"
      className={`flex items-center gap-2 ${size === 'md' ? 'w-full flex-wrap' : 'shrink-0'}`}
    >
      <button
        type="button"
        data-testid="potential-resales-toggle"
        onClick={onPotentialToggle}
        aria-pressed={potentialOnly}
        className={`inline-flex items-center gap-1.5 ${h} px-3 ${text} font-medium rounded-full ring-1 transition-colors
          ${
            potentialOnly
              ? 'bg-emerald-600 text-white ring-emerald-600 dark:bg-emerald-500 dark:ring-emerald-500'
              : 'bg-white dark:bg-night2 ring-rule dark:ring-dusk text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'
          }`}
      >
        <TrendingUp size={15} strokeWidth={2} />
        <span>Potential resales</span>
      </button>

      <div
        data-testid="confidence-filter"
        className={`inline-flex p-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk ${size === 'md' ? '' : 'shrink-0'}`}
      >
        {CONFIDENCE_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            data-testid={`confidence-${opt.id}`}
            onClick={() => onConfidenceChange(opt.id)}
            aria-pressed={confidenceFilter === opt.id}
            className={`px-3 ${h} ${text} font-medium rounded-full transition-colors
              ${
                confidenceFilter === opt.id
                  ? 'bg-white text-ink shadow-sm dark:bg-night2 dark:text-bone'
                  : 'text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'
              }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
