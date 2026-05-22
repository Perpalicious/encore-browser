import { useState, useEffect } from 'react';
import type { Density } from '../lib/types';

function getColumns(density: Density): number {
  if (typeof window === 'undefined') return 1;
  const w = window.innerWidth;
  if (density === 'compact') {
    if (w >= 1280) return 5;
    if (w >= 1024) return 4;
    if (w >= 640) return 3;
    return 2;
  } else {
    if (w >= 1280) return 4;
    if (w >= 1024) return 3;
    if (w >= 640) return 2;
    return 1;
  }
}

export function useColumns(density: Density): number {
  const [cols, setCols] = useState(() => getColumns(density));

  useEffect(() => {
    setCols(getColumns(density));
    const onResize = () => setCols(getColumns(density));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [density]);

  return cols;
}
