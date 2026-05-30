import { useState, useEffect } from 'react';

/**
 * Returns a debounced copy of `value` that only updates after `delayMs` of
 * no further changes. Used to keep the search input responsive while deferring
 * the (heavier) fuzzy filter pass at 20k items.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}
