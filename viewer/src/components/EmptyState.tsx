import { Sparkles, X } from 'lucide-react';
import type { Tab } from '../lib/types';

interface Props {
  tab: Tab;
  onClear: () => void;
}

const COPY: Record<Tab, { title: string; body: string }> = {
  watched: {
    title: 'No watched lots yet',
    body: 'Tap the star on any card to keep an eye on it. Watched lots stay here even when filters change.',
  },
  bat: {
    title: "No matches in Bat's List",
    body: 'Try a different bucket — or clear the filters to see everything.',
  },
  all: {
    title: 'Nothing matches those filters',
    body: 'Loosen the search, switch days, or pick a different category.',
  },
};

export function EmptyState({ tab, onClear }: Props) {
  const copy = COPY[tab];
  return (
    <div className="mx-auto max-w-md text-center py-20 md:py-28">
      <div className="mx-auto mb-5 h-14 w-14 grid place-items-center rounded-full bg-paper2 dark:bg-coal text-ember">
        <Sparkles size={24} strokeWidth={1.75} />
      </div>
      <h2 className="font-serif text-[26px] leading-tight text-ink dark:text-bone">{copy.title}</h2>
      <p className="mt-2 text-[14px] text-ink2 dark:text-bone2 leading-relaxed">{copy.body}</p>
      {tab !== 'watched' && (
        <button
          onClick={onClear}
          className="mt-6 inline-flex items-center gap-2 h-11 px-5 rounded-full bg-ember hover:bg-ember2 text-white font-medium text-[14px]"
        >
          <X size={16} />
          Clear filters
        </button>
      )}
    </div>
  );
}
