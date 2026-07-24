import { Heart } from 'lucide-react';

interface Props {
  personalOnly: boolean;
  onPersonalToggle: () => void;
  /** 'sm' for the dense desktop header, 'md' for the mobile filter panel. */
  size?: 'sm' | 'md';
}

/**
 * The "Personal picks" toggle: shows only lots the personal-match pass flagged
 * (personal_match === true). Orthogonal to category/bucket — it narrows within
 * whatever tab / category / search view is active, like the resale filters.
 */
export function PersonalFilter({ personalOnly, onPersonalToggle, size = 'sm' }: Props) {
  const h = size === 'sm' ? 'h-[34px]' : 'h-9';
  return (
    <button
      type="button"
      data-testid="personal-picks-toggle"
      onClick={onPersonalToggle}
      aria-pressed={personalOnly}
      className={`inline-flex items-center gap-1.5 ${h} px-3 text-[13px] font-medium rounded-full ring-1 transition-colors shrink-0
        ${
          personalOnly
            ? 'bg-violet-600 text-white ring-violet-600 dark:bg-violet-500 dark:ring-violet-500'
            : 'bg-white dark:bg-night2 ring-rule dark:ring-dusk text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'
        }`}
    >
      <Heart size={15} strokeWidth={2} className={personalOnly ? 'fill-current' : ''} />
      <span>Personal picks</span>
    </button>
  );
}
