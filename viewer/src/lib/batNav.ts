import type { Lot } from './types';

export const UNGROUPED = 'Other';

export interface SubtypeNode {
  name: string;
  count: number; // distinct lots in this bucket carrying this subtype
}

export interface BucketNode {
  name: string;
  count: number; // distinct lots in this bucket
  /**
   * The free-form level under the bucket, largest first. Empty for a bundle
   * built before the flagging pass emitted `bat_subtype`, which is what the
   * viewer feature-detects on to keep the drill-down at two panes.
   */
  subtypes: SubtypeNode[];
}

export interface GroupNode {
  name: string;
  count: number; // distinct lots with ≥1 bucket in this group
  buckets: BucketNode[]; // buckets in this group that have items, sorted by name
}

/**
 * Build the two-level Bat's List navigation tree (groups → buckets) from the
 * flagged lots and the bundle's bucket→group map.
 *
 * Counts reflect membership: a lot in two buckets across two groups counts in
 * both groups; a lot in two buckets within one group counts once for the group
 * but in each bucket. Only groups/buckets that actually contain items appear.
 * Groups are returned in `groupOrder` (buckets.yaml order, "Other" last).
 */
export function buildBatNav(
  lots: Lot[],
  bucketGroups: Record<string, string>,
  groupOrder: string[]
): GroupNode[] {
  // group -> set of lot_numbers (distinct), and group -> bucket -> set
  const groupLots = new Map<string, Set<string>>();
  const groupBucketLots = new Map<string, Map<string, Set<string>>>();
  // group -> bucket -> subtype -> set. Same single pass; a lot in two buckets
  // contributes its subtype to each, exactly like the bucket counts above.
  const groupBucketSubtypeLots = new Map<string, Map<string, Map<string, Set<string>>>>();

  for (const lot of lots) {
    if (!lot.is_bat) continue;
    for (const bucket of lot.bat_buckets) {
      const group = bucketGroups[bucket] ?? UNGROUPED;

      if (!groupLots.has(group)) groupLots.set(group, new Set());
      groupLots.get(group)!.add(lot.lot_number);

      if (!groupBucketLots.has(group)) groupBucketLots.set(group, new Map());
      const buckets = groupBucketLots.get(group)!;
      if (!buckets.has(bucket)) buckets.set(bucket, new Set());
      buckets.get(bucket)!.add(lot.lot_number);

      const subtype = lot.bat_subtype || null;
      if (subtype) {
        if (!groupBucketSubtypeLots.has(group)) groupBucketSubtypeLots.set(group, new Map());
        const byBucket = groupBucketSubtypeLots.get(group)!;
        if (!byBucket.has(bucket)) byBucket.set(bucket, new Map());
        const bySubtype = byBucket.get(bucket)!;
        if (!bySubtype.has(subtype)) bySubtype.set(subtype, new Set());
        bySubtype.get(subtype)!.add(lot.lot_number);
      }
    }
  }

  // Order groups: those in groupOrder first (in order), then any leftover
  // groups (e.g. "Other" if not already listed) appended alphabetically.
  const ordered: string[] = [];
  for (const g of groupOrder) {
    if (groupLots.has(g)) ordered.push(g);
  }
  for (const g of [...groupLots.keys()].sort()) {
    if (!ordered.includes(g)) ordered.push(g);
  }

  return ordered.map((group) => {
    const bucketMap = groupBucketLots.get(group)!;
    const subtypeMap = groupBucketSubtypeLots.get(group);
    const buckets: BucketNode[] = [...bucketMap.entries()]
      .map(([name, lotSet]) => ({
        name,
        count: lotSet.size,
        // Largest first: subtypes are free-form, so the useful ones are the
        // ones the pass reused, and a long tail of one-offs sorts itself out.
        subtypes: [...(subtypeMap?.get(name)?.entries() ?? [])]
          .map(([sub, subLots]) => ({ name: sub, count: subLots.size }))
          .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
    return {
      name: group,
      count: groupLots.get(group)!.size,
      buckets,
    };
  });
}
