import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * The transient confirmation strip — docs/design/README.md § "Toast".
 *
 * Swipe triage commits are invisible by design: the row simply leaves the
 * results. The toast is what tells you it happened, so it fires on every
 * commit, not just failures.
 */

const TOAST_MS = 1500;

export function useToast(): [string | null, (message: string) => void] {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((next: string) => {
    setMessage(next);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), TOAST_MS);
  }, []);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  return [message, show];
}

export function Toast({ message }: { message: string }) {
  return (
    <div
      data-testid="toast"
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        left: '50%',
        transform: 'translateX(-50%)',
        bottom: 26,
        zIndex: 80,
        padding: '9px 16px',
        borderRadius: 22,
        background: 'var(--s3)',
        border: '1px solid var(--line)',
        boxShadow: 'var(--sh)',
        fontSize: '12.5px',
        fontWeight: 500,
        color: 'var(--text)',
        whiteSpace: 'nowrap',
        animation: 'sheetup .18s ease-out',
      }}
    >
      {message}
    </div>
  );
}
