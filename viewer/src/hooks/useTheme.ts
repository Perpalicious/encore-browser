import { useState, useEffect } from 'react';

function getInitialDark(): boolean {
  try {
    const stored = localStorage.getItem('encore_theme');
    if (stored === 'dark') return true;
    if (stored === 'light') return false;
  } catch {
    // ignore
  }
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  return false;
}

export function useTheme(): [boolean, () => void] {
  const [dark, setDark] = useState(getInitialDark);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    const color = dark ? '#0F1012' : '#FAF6EE';
    let meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = color;
    try {
      localStorage.setItem('encore_theme', dark ? 'dark' : 'light');
    } catch {
      // ignore
    }
  }, [dark]);

  const toggle = () => setDark((d) => !d);
  return [dark, toggle];
}
