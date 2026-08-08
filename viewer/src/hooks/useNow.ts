import { useState, useEffect } from 'react';

/**
 * A clock that re-renders on an interval.
 *
 * Lots close while you are looking at the page — that is the entire point of
 * showing closing times — so "has this ended" cannot be decided once at load.
 * Everything time-dependent reads this value rather than calling `Date.now()`
 * inline, which would compute a fresh answer on every render and still never
 * update on its own.
 *
 * Pass `enabled: false` when the bundle carries no closing times at all: there
 * is then nothing to re-render for, and a timer ticking over 26k lots for a
 * week would be pure waste.
 */
export function useNow(enabled: boolean, intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!enabled) return;
    // Catch up immediately: a tab restored from the background can be many
    // intervals stale, and waiting up to 30s to admit that would show lots as
    // live when they have long closed.
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    const onVisible = () => {
      if (document.visibilityState === 'visible') setNow(Date.now());
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [enabled, intervalMs]);

  return now;
}
