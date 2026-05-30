import { describe, it, expect } from 'vitest';
import { buildBatNav, UNGROUPED } from './batNav';
import type { Lot } from './types';

function lot(lot_number: string, bat_buckets: string[], is_bat = true): Lot {
  return {
    day: 'Sunday',
    lot_number,
    title: `Lot ${lot_number}`,
    description: '',
    condition: null,
    thumb_url: '',
    image_url: '',
    lot_url: '',
    category: '',
    subcategory: '',
    category_path: [],
    is_bat,
    bat_buckets,
    confidence: 'low',
  };
}

// Hand-authored fixture: 8 groups, known buckets, multi-bucket membership,
// and one legacy bucket that should fall through to "Other".
const GROUP_ORDER = [
  'Kitchen & dining',
  'Tools & garage',
  'Outdoor & garden',
  'Home & bedroom',
  'Cleaning & storage',
  'Toys & games',
  'Electronics & gaming',
  'Sports & fitness',
];

const BUCKET_GROUPS: Record<string, string> = {
  'Kitchen appliances': 'Kitchen & dining',
  'Brand chef knives': 'Kitchen & dining',
  'Power tools': 'Tools & garage',
  'Lawn equipment': 'Outdoor & garden',
  'Bed linens': 'Home & bedroom',
  'Cleaning supplies & tools': 'Cleaning & storage',
  'Lego': 'Toys & games',
  'Smart home': 'Electronics & gaming',
  'Home gym & weightlifting': 'Sports & fitness',
  // 'LegacyThing' intentionally absent → should resolve to "Other"
};

const LOTS: Lot[] = [
  lot('1', ['Kitchen appliances']),
  lot('2', ['Brand chef knives']),
  lot('3', ['Kitchen appliances', 'Brand chef knives']), // 2 buckets, same group
  lot('4', ['Power tools']),
  lot('5', ['Lawn equipment']),
  lot('6', ['Bed linens']),
  lot('7', ['Cleaning supplies & tools']),
  lot('8', ['Lego']),
  lot('9', ['Smart home']),
  lot('10', ['Home gym & weightlifting']),
  lot('11', ['Power tools', 'Smart home']), // 2 buckets across 2 groups
  lot('12', ['LegacyThing']), // unknown bucket → Other
  lot('13', ['Kitchen appliances'], false), // not is_bat → excluded
];

describe('buildBatNav', () => {
  const nav = buildBatNav(LOTS, BUCKET_GROUPS, GROUP_ORDER);
  const byName = Object.fromEntries(nav.map((g) => [g.name, g]));

  it('renders all 8 populated groups plus Other, in buckets.yaml order with Other last', () => {
    const names = nav.map((g) => g.name);
    expect(names).toEqual([
      'Kitchen & dining',
      'Tools & garage',
      'Outdoor & garden',
      'Home & bedroom',
      'Cleaning & storage',
      'Toys & games',
      'Electronics & gaming',
      'Sports & fitness',
      UNGROUPED,
    ]);
  });

  it('group count is distinct lots with ≥1 bucket in the group', () => {
    // Kitchen & dining: lots 1,2,3 (lot 3 has two kitchen buckets → counts once)
    expect(byName['Kitchen & dining'].count).toBe(3);
    // Tools & garage: lots 4, 11
    expect(byName['Tools & garage'].count).toBe(2);
    // Electronics & gaming: lots 9, 11
    expect(byName['Electronics & gaming'].count).toBe(2);
  });

  it('a lot in two buckets across two groups counts in both groups', () => {
    // lot 11 is in Power tools (Tools & garage) AND Smart home (Electronics)
    expect(byName['Tools & garage'].count).toBe(2); // lots 4, 11
    expect(byName['Electronics & gaming'].count).toBe(2); // lots 9, 11
  });

  it('per-bucket counts reflect membership', () => {
    const kitchen = byName['Kitchen & dining'];
    const appliances = kitchen.buckets.find((b) => b.name === 'Kitchen appliances')!;
    const knives = kitchen.buckets.find((b) => b.name === 'Brand chef knives')!;
    // lots 1,3 in appliances; lots 2,3 in knives
    expect(appliances.count).toBe(2);
    expect(knives.count).toBe(2);
    // buckets sorted by name
    expect(kitchen.buckets.map((b) => b.name)).toEqual(['Brand chef knives', 'Kitchen appliances']);
  });

  it('unknown buckets fall through to Other', () => {
    expect(byName[UNGROUPED].count).toBe(1);
    expect(byName[UNGROUPED].buckets.map((b) => b.name)).toEqual(['LegacyThing']);
  });

  it('excludes non-bat lots', () => {
    // lot 13 (Kitchen appliances, is_bat=false) must not inflate the count
    expect(byName['Kitchen & dining'].buckets.find((b) => b.name === 'Kitchen appliances')!.count).toBe(2);
  });
});
