import { ChevronLeft, Sparkles } from 'lucide-react';
import type { GroupNode } from '../lib/batNav';

interface Props {
  groups: GroupNode[];
  selectedGroup: string | null;
  onSelectGroup: (group: string) => void;
  onSelectBucket: (bucket: string) => void;
  onBack: () => void;
}

const countPill =
  'ml-1.5 inline-flex items-center justify-center min-w-[22px] h-5 px-1.5 rounded-full ' +
  'text-[11px] font-semibold tabular-nums bg-paper2 dark:bg-coal text-ink2 dark:text-bone2';

const chip =
  'inline-flex items-center h-10 px-4 rounded-full text-[14px] font-medium ' +
  'bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-ink dark:text-bone ' +
  'hover:ring-ember hover:text-ember dark:hover:text-ember transition-colors';

/**
 * Two-level Bat's List navigation surface: groups → buckets. Both levels wrap
 * (flex-wrap) so there is no hidden horizontal overflow — everything is
 * reachable without scroll tricks. Selecting a bucket hands off to the item
 * grid (handled by the parent).
 */
export function BatGroupNav({
  groups,
  selectedGroup,
  onSelectGroup,
  onSelectBucket,
  onBack,
}: Props) {
  const group = selectedGroup ? groups.find((g) => g.name === selectedGroup) : null;

  return (
    <div data-testid="bat-group-nav" className="py-2">
      {group ? (
        <>
          <div className="flex items-center gap-3 mb-4">
            <button
              type="button"
              data-testid="bat-back-to-groups"
              onClick={onBack}
              className="inline-flex items-center gap-1 h-9 pl-2 pr-3.5 rounded-full text-[13px] font-medium text-ink2 dark:text-bone2 bg-paper2 dark:bg-coal hover:bg-rule dark:hover:bg-dusk ring-1 ring-rule/60 dark:ring-dusk transition-colors"
            >
              <ChevronLeft size={16} />
              All groups
            </button>
            <h2 className="font-serif text-[20px] md:text-[22px] text-ink dark:text-bone">
              {group.name}
              <span className="ml-2 text-[13px] font-sans text-ink2/70 dark:text-bone2/70">
                {group.count} {group.count === 1 ? 'lot' : 'lots'}
              </span>
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {group.buckets.map((b) => (
              <button
                key={b.name}
                type="button"
                data-testid="bat-bucket"
                data-bucket={b.name}
                onClick={() => onSelectBucket(b.name)}
                className={chip}
              >
                {b.name}
                <span className={countPill}>{b.count}</span>
              </button>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2 mb-4 text-ink dark:text-bone">
            <Sparkles size={20} className="text-ember" strokeWidth={2} />
            <h2 className="font-serif text-[20px] md:text-[22px]">Bat's List — pick a group</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {groups.map((g) => (
              <button
                key={g.name}
                type="button"
                data-testid="bat-group"
                data-group={g.name}
                onClick={() => onSelectGroup(g.name)}
                className={chip}
              >
                {g.name}
                <span className={countPill}>{g.count}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
