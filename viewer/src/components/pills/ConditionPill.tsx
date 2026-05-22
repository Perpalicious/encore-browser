import type { Condition } from '../../lib/types';

const CONDITION_STYLES: Record<Condition, string> = {
  New: 'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:ring-emerald-800/60',
  'Like New':
    'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:ring-emerald-800/60',
  Good: 'bg-paper2 text-ink2 ring-rule dark:bg-coal dark:text-bone2 dark:ring-dusk',
  Fair: 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:ring-amber-800/60',
  'Heavily Used':
    'bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-900/30 dark:text-rose-200 dark:ring-rose-800/60',
};

interface Props {
  value: Condition | null;
  size?: 'md' | 'sm';
  className?: string;
}

export function ConditionPill({ value, size = 'md', className = '' }: Props) {
  if (!value) return null;
  const sz = size === 'sm' ? 'text-[10px] px-1.5 py-[2px]' : 'text-[11px] px-2 py-[3px]';
  return (
    <span
      className={`inline-flex items-center font-medium tracking-wide uppercase rounded-full ring-1 ${sz} ${CONDITION_STYLES[value]} ${className}`}
    >
      {value}
    </span>
  );
}
