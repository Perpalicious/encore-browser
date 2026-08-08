import type { GroupNode } from '../lib/batNav';
import { DrillPopover } from './DrillPopover';

/**
 * Bat's List bucket switcher.
 *
 * The full-screen picker (BatEmptyState) is a fine way to CHOOSE a bucket when
 * you have none, but a terrible way to CHANGE one: it meant clearing the bucket
 * entirely and drilling group → bucket again. This is the same group → bucket
 * tree in the rail's drill-down, so switching is one click to open and one to
 * pick, without losing the grid behind it.
 *
 * "All buckets" clears the selection, which lands you back on the picker.
 */

interface Props {
  groups: GroupNode[];
  group: string | null;
  bucket: string | null;
  onGroupChange: (g: string | null) => void;
  onBucketChange: (b: string | null) => void;
  onClose: () => void;
  sheet: boolean;
}

export function BucketPopover({
  groups,
  group,
  bucket,
  onGroupChange,
  onBucketChange,
  onClose,
  sheet,
}: Props) {
  // The picker's group state can be stale or unset — you can arrive here from a
  // shared link that carries only the bucket. Fall back to whichever group
  // actually holds the current bucket so the right pane opens on it.
  const owning = bucket ? groups.find((g) => g.buckets.some((b) => b.name === bucket)) : undefined;
  const activeName = group ?? owning?.name ?? null;
  const active = groups.find((g) => g.name === activeName) ?? null;

  return (
    <DrillPopover
      testId="bucket-popover"
      ariaLabel="Bat's List buckets"
      clearLabel="All buckets"
      clearTestId="bucket-all"
      clearActive={bucket === null}
      onClear={() => onBucketChange(null)}
      sheet={sheet}
      onClose={onClose}
      left={{
        testId: 'bucket-level-0',
        items: groups.map((g) => ({ name: g.name, count: g.count })),
        activeName,
        onPick: (name) => onGroupChange(name),
      }}
      right={{
        testId: 'bucket-level-1',
        items: active ? active.buckets.map((b) => ({ name: b.name, count: b.count })) : [],
        activeName: bucket,
        empty: 'Pick a group',
        onPick: (name) => {
          onGroupChange(activeName);
          onBucketChange(name);
          onClose();
        },
      }}
    />
  );
}
