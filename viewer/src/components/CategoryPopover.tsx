import type { CatNode } from '../lib/categoryTree';
import { nodeAtPath } from '../lib/categoryTree';
import { DrillPopover, type DrillItem } from './DrillPopover';

/**
 * Category drill-down — docs/design/README.md § "Category drill-down".
 *
 * Categories on the left with their lot counts, sub-categories of the selection
 * on the right. Picking a sub-category closes the popover; "All categories"
 * clears both. Replaces the cascading <select> chain, which needed one
 * interaction per level and gave no counts.
 *
 * The tree is deeper than two levels in places (20,122 lots sit at depth 3),
 * but the drill-down deliberately stops at sub-category: below that the counts
 * get too thin to be a useful way to navigate, and search covers it.
 *
 * The shell itself lives in DrillPopover, shared with the Bat's List
 * group → bucket picker.
 */

interface Props {
  tree: CatNode;
  /** Selected prefix, root → leaf. Empty = "All categories". */
  selected: string[];
  onChange: (path: string[]) => void;
  onClose: () => void;
  sheet: boolean;
}

/** Child names of the node at `path`, largest first, with counts. */
function childrenWithCounts(tree: CatNode, path: string[]): DrillItem[] {
  const node = nodeAtPath(tree, path);
  if (!node) return [];
  return Object.entries(node.children)
    .map(([name, child]) => ({ name, count: child.count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function CategoryPopover({ tree, selected, onChange, onClose, sheet }: Props) {
  const activeCat = selected[0] ?? null;

  return (
    <DrillPopover
      testId="category-popover"
      ariaLabel="Categories"
      clearLabel="All categories"
      clearTestId="category-all"
      clearActive={selected.length === 0}
      onClear={() => onChange([])}
      sheet={sheet}
      onClose={onClose}
      left={{
        testId: 'category-level-0',
        items: childrenWithCounts(tree, []),
        activeName: activeCat,
        onPick: (name) => onChange([name]),
      }}
      right={{
        testId: 'category-level-1',
        items: activeCat ? childrenWithCounts(tree, [activeCat]) : [],
        activeName: selected[1] ?? null,
        empty: activeCat ? 'No sub-categories' : 'Pick a category',
        onPick: (name) => {
          onChange([activeCat!, name]);
          onClose();
        },
      }}
    />
  );
}
