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
 */
export function useCoarsePointer(): boolean {
  return useMediaQuery('(pointer: coarse)');
}
