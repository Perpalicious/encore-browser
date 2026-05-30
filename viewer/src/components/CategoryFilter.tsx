import { ChevronDown } from 'lucide-react';
import type { CatNode } from '../lib/categoryTree';
import { childrenAtPath } from '../lib/categoryTree';

interface Props {
  tree: CatNode;
  /** Selected category prefix, root → leaf. Empty = "All categories". */
  selected: string[];
  onChange: (path: string[]) => void;
  /** Visual size: 'sm' for the dense desktop header, 'md' for the mobile panel. */
  size?: 'sm' | 'md';
}

/**
 * Hierarchical category filter rendered as cascading drill-down selects.
 *
 * One <select> is shown per level the user has drilled into, plus one more for
 * the next level whenever the current node has children. Picking a value at
 * level i sets the prefix to selected[0..i-1] + value (dropping anything
 * deeper); picking the "All …" sentinel truncates the prefix to that level.
 *
 * A lot matches when its category_path starts with `selected` (see filter.ts).
 */
export function CategoryFilter({ tree, selected, onChange, size = 'sm' }: Props) {
  // Build the list of levels to render: one per already-selected segment, plus
  // a trailing "drill deeper" select when the deepest selected node has kids.
  const levels: { options: string[]; value: string; index: number }[] = [];
  for (let i = 0; ; i++) {
    const prefix = selected.slice(0, i);
    const options = childrenAtPath(tree, prefix);
    if (options.length === 0) break; // no further drill-down available
    levels.push({ options, value: selected[i] ?? '', index: i });
    if (selected[i] === undefined) break; // trailing (not-yet-chosen) level
  }

  const height = size === 'sm' ? 'h-10' : 'h-10';
  const text = size === 'sm' ? 'text-[13px]' : 'text-[14px]';

  const handleChange = (levelIndex: number, value: string) => {
    const next = selected.slice(0, levelIndex);
    if (value !== '') next.push(value);
    onChange(next);
  };

  return (
    <div
      data-testid="category-filter"
      className={`flex items-center gap-1.5 ${size === 'md' ? 'flex-wrap w-full' : 'flex-wrap'}`}
    >
      {levels.map((lvl) => {
        // Sentinel label: top level says "All categories"; deeper levels say
        // "All <parent>" so picking it means "stop at the parent".
        const sentinel =
          lvl.index === 0 ? 'All categories' : `All ${selected[lvl.index - 1]}`;
        return (
          <div key={lvl.index} className="relative shrink-0">
            <select
              data-testid={`category-level-${lvl.index}`}
              value={lvl.value}
              onChange={(e) => handleChange(lvl.index, e.target.value)}
              className={`appearance-none ${height} pl-3.5 pr-9 max-w-[200px] rounded-full bg-white dark:bg-night2 ring-1 ring-rule dark:ring-dusk ${text} font-medium text-ink dark:text-bone focus:ring-2 focus:ring-ember focus:outline-none cursor-pointer truncate`}
            >
              <option value="">{sentinel}</option>
              {lvl.options.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={15}
              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink2 dark:text-bone2"
            />
          </div>
        );
      })}
    </div>
  );
}
