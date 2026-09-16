import { useState, useEffect } from 'react';

/**
 * A boolean remembered in localStorage — for per-viewer conveniences like
 * "leave the legend open". Same shape as usePersistedSet: every storage call
 * is wrapped, and the initializer must also survive an environment with no
 * `localStorage` at all (the render tests run under node).
 */
export function usePersistedBool(
  storageKey: string,
  initial: boolean
): [boolean, (v: boolean | ((prev: boolean) => boolean)) => void] {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw === '1') return true;
      if (raw === '0') return false;
    } catch {
      // ignore
    }
    return initial;
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, value ? '1' : '0');
    } catch {
      // ignore
    }
  }, [value, storageKey]);

  return [value, setValue];
}
