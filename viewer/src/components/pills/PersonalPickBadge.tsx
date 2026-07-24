import { Heart } from 'lucide-react';

interface Props {
  /** match_strength when known — folded into the label/tooltip. */
  strength?: string | null;
  size?: 'md' | 'sm';
  /** Show "— {strength} match" inline (expand panel) vs tooltip-only (card). */
  showStrength?: boolean;
}

/**
 * The personal-pick badge: filled heart on violet. Deliberately its own look —
 * not confusable with the ember Bat's List bucket chips or the
 * emerald/amber/rose resale chips.
 */
export function PersonalPickBadge({ strength, size = 'md', showStrength = false }: Props) {
  const sz = size === 'sm' ? 'text-[10px] px-1.5 py-[2px]' : 'text-[11px] px-2 py-[3px]';
  const iconSize = size === 'sm' ? 10 : 11;
  const label = strength ? `Personal pick — ${strength} match` : 'Personal pick';
  return (
    <span
      data-testid="personal-badge"
      title={label}
      className={`inline-flex items-center gap-1 font-medium rounded-full ${sz} bg-violet-500/10 text-violet-700 ring-1 ring-violet-500/25 dark:bg-violet-400/15 dark:text-violet-300 dark:ring-violet-400/30`}
    >
      <Heart size={iconSize} strokeWidth={2} className="fill-current" />
      <span>{showStrength ? label : 'Personal pick'}</span>
    </span>
  );
}
