import { useState, useEffect } from 'react';

export function usePersistedSet(storageKey: string): [Set<string>, (id: string) => void] {
  const [set, setSet] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const arr = JSON.parse(raw) as string[];
        return new Set(arr);
      }
    } catch {
      // ignore
    }
    return new Set<string>();
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(Array.from(set)));
    } catch {
      // ignore
    }
  }, [set, storageKey]);

  const toggle = (id: string) => {
    setSet((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return [set, toggle];
}
