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
    // Two mechanisms, deliberately kept in sync:
    //   data-theme — what the design tokens key off (src/styles/tokens.css);
    //                dark is :root's default, light is the [data-theme] override.
    //   .dark      — what Tailwind's `dark:` variant keys off; the pre-redesign
    //                components still depend on it. Drops out once they're ported.
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    document.documentElement.classList.toggle('dark', dark);
    const color = dark ? '#0a0a0d' : '#f6f3ec';
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
