import { Check } from 'lucide-react';

interface Props {
  buckets: string[];
  selected: string;
  onSelect: (bucket: string) => void;
}

export function BucketChipRow({ buckets, selected, onSelect }: Props) {
  return (
    <div className="-mx-4 md:-mx-6 px-4 md:px-6 pt-3 pb-3 border-t border-rule/60 dark:border-dusk/60 animate-slideDown">
      <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
        {buckets.map((b) => (
          <button
            key={b}
            onClick={() => onSelect(b)}
            aria-pressed={selected === b}
            className={`shrink-0 inline-flex items-center gap-1.5 h-9 px-3.5 rounded-full text-[13px] font-medium transition-all
              ${
                selected === b
                  ? 'bg-ink text-paper dark:bg-bone dark:text-night'
                  : 'bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-ink2 dark:text-bone2 hover:text-ink dark:hover:text-bone'
              }`}
          >
            {selected === b && b !== 'All' && <Check size={13} strokeWidth={2.5} />}
            {b}
          </button>
        ))}
      </div>
    </div>
  );
}
