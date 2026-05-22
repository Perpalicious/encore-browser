import { Sparkles } from 'lucide-react';

interface Props {
  active: boolean;
  onClick: () => void;
  label: string;
  badge?: number;
  sparkle?: boolean;
  testId?: string;
}

export function TabButton({ active, onClick, label, badge, sparkle, testId }: Props) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      data-testid={testId}
      className={`relative inline-flex items-center gap-1.5 h-11 px-3 md:px-4 text-[14px] md:text-[15px] font-medium transition-colors
        ${active ? 'text-ink dark:text-bone' : 'text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'}`}
    >
      {sparkle && (
        <Sparkles size={14} className={active ? 'text-ember' : 'text-ember/70'} strokeWidth={2} />
      )}
      <span>{label}</span>
      {typeof badge === 'number' && (
        <span
          className={`inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-semibold tabular-nums
          ${active ? 'bg-ember text-white' : 'bg-paper2 dark:bg-coal text-ink2 dark:text-bone2'}`}
        >
          {badge}
        </span>
      )}
      {/* underline indicator */}
      <span
        className={`absolute left-2 right-2 -bottom-px h-[2px] rounded-full transition-all duration-200
          ${active ? 'bg-ember opacity-100' : 'opacity-0 bg-ember'}`}
      />
    </button>
  );
}
