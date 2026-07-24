import type { Lot } from './types';

/**
 * Personal-match helpers. The personal-match pass covers only some bundles
 * (and flags only some lots), so every consumer must tolerate missing data:
 * `isPersonalPick` is the gate, and it is true ONLY for an explicit
 * `personal_match: true` — null, undefined, and false all mean "not a pick".
 */

/** True only when the personal-match pass flagged this lot. */
export function isPersonalPick(lot: Lot): boolean {
  return lot.personal_match === true;
}

/** Badge/tooltip label, e.g. "Personal pick — strong match". */
export function personalPickLabel(lot: Lot): string {
  return lot.match_strength
    ? `Personal pick — ${lot.match_strength} match`
    : 'Personal pick';
}
