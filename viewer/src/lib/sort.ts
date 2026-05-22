import type { Lot } from './types';

export function sortLots(lots: Lot[]): Lot[] {
  return lots.slice().sort((a, b) => {
    // 1. is_bat first
    if (a.is_bat !== b.is_bat) return a.is_bat ? -1 : 1;
    // 2. Sunday before Monday
    if (a.day !== b.day) return a.day === 'Sunday' ? -1 : 1;
    // 3. lot_number ascending
    return a.lot_number.localeCompare(b.lot_number);
  });
}
