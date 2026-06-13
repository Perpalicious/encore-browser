import { ChevronDown, Sparkles } from 'lucide-react';
import type { GroupNode } from '../lib/batNav';

interface Props {
  groups: GroupNode[];
  /** Currently selected bucket, or null for the "pick a bucket" prompt. */
  value: string | null;
  onChange: (bucket: string | null) => void;
}

/**
 * Bat's List bucket picker: a single native <select> whose options are grouped
 * by <optgroup> (one per Bat's List group, in buckets.yaml order). Picking a
 * bucket shows its items immediately; switching to another bucket is one change
 * of the dropdown — there is no drill-in or back-out. Counts ride alongside
 * each bucket name, e.g. "Dinnerware (10)".
 */
export function BatBucketSelect({ groups, value, onChange }: Props) {
  return (
    <div data-testid="bat-bucket-select" className="flex items-center gap-2">
      <Sparkles size={18} className="text-ember shrink-0" strokeWidth={2} />
      <div className="relative flex-1 min-w-0 sm:flex-initial sm:w-[340px]">
        <select
          data-testid="bat-bucket-dropdown"
          aria-label="Bat's List bucket"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
          className="appearance-none w-full h-10 pl-4 pr-10 rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk text-[14px] font-medium text-ink dark:text-bone focus:ring-2 focus:ring-ember focus:outline-none cursor-pointer truncate"
        >
          <option value="">Pick a bucket…</option>
          {groups.map((g) => (
            <optgroup key={g.name} label={g.name}>
              {g.buckets.map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name} ({b.count})
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <ChevronDown
          size={16}
          className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-ink2 dark:text-bone2"
        />
      </div>
    </div>
  );
}
