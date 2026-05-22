import { Sparkles } from 'lucide-react';

interface Props {
  label: string;
  extra?: number;
  size?: 'md' | 'sm';
}

export function BatBucketPill({ label, extra = 0, size = 'md' }: Props) {
  const sz = size === 'sm' ? 'text-[10px] px-1.5 py-[2px]' : 'text-[11px] px-2 py-[3px]';
  const iconSize = size === 'sm' ? 10 : 11;
  return (
    <span
      className={`inline-flex items-center gap-1 font-medium rounded-full ${sz} bg-ember/10 text-ember2 ring-1 ring-ember/20 dark:bg-ember/15 dark:text-ember dark:ring-ember/30`}
    >
      <Sparkles size={iconSize} strokeWidth={2} />
      <span>{label}</span>
      {extra > 0 && <span className="opacity-70">+{extra}</span>}
    </span>
  );
}
