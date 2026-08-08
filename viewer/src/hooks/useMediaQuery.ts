import { useState, useEffect } from 'react';

/** Subscribe to a media query. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia(query).matches
      : false
  );

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/**
 * Layout is chosen by WIDTH — below 760px is the mobile layout.
 * docs/design/README.md § "Input mode vs. layout mode".
 */
export function useMobileLayout(): boolean {
  return useMediaQuery('(max-width: 759px)');
}

/**
 * Affordances are chosen by INPUT, not width. This matters for tablets: an iPad
 * is 768–1366pt, so it gets the desktop grid, but it must not inherit desktop
 * interaction assumptions — overlays become bottom sheets, hit areas grow.
 *
 * Deliberately the STRICT test (the primary pointer is coarse): a touchscreen
 * laptop driven with a mouse must not get bottom sheets and 44px rows.
 */
export function useCoarsePointer(): boolean {
  return useMediaQuery('(pointer: coarse)');
}

/**
 * Whether a touch gesture is possible at all — the PERMISSIVE test, and the one
 * that gates swipe.
 *
 * Separate from `useCoarsePointer` because the two get their wrong answers in
 * opposite directions and at opposite cost. Enabling swipe where it is not
 * wanted costs nothing: a mouse user never drags a card sideways, and if they
 * do it watches a lot, says so in a toast, and undoes on a repeat. Enabling
 * SHEETS where they are not wanted is a visible regression. So swipe accepts
 * `any-pointer: coarse` (a touchscreen among several inputs) and the
 * maxTouchPoints fallback, which covers an iPad whose desktop-class browsing
 * reports itself as a fine pointer.
 *
 * Measured under emulation (2026-08-08), iPad Pro 11 / iPad gen 7 / Galaxy Tab
 * S4 all report `pointer: coarse` true, `hover: hover` false, maxTouchPoints 1
 * — so on those the strict test would have been enough. This stays permissive
 * for real iPadOS Safari, which emulation does not fully stand in for. The
 * actual reason swipe did nothing on an iPad was elsewhere: a tablet is wider
 * than 760px, so it gets the desktop layout and opens in CARDS, and the
 * gesture only existed on rows.
 */
export function useTouchCapable(): boolean {
  const anyCoarse = useMediaQuery('(any-pointer: coarse)');
  const [touchPoints] = useState(
    () => typeof navigator !== 'undefined' && navigator.maxTouchPoints > 0
  );
  return anyCoarse || touchPoints;
}
