import type { Density } from '../lib/types';

interface Props {
  density: Density;
}

export function SkeletonCard({ density }: Props) {
  const compact = density === 'compact';
  return (
    <div className="rounded-2xl bg-white dark:bg-night2 ring-1 ring-rule/60 dark:ring-dusk overflow-hidden shadow-card dark:shadow-cardDark">
      <div
        className={`${compact ? 'aspect-[5/4]' : 'aspect-[4/3]'} bg-paper2 dark:bg-coal shimmer`}
      />
      <div className="px-4 pt-3.5 pb-4 space-y-2.5">
        <div className="flex justify-between">
          <div className="h-3 w-16 rounded bg-paper2 dark:bg-coal shimmer" />
          <div className="h-3 w-12 rounded bg-paper2 dark:bg-coal shimmer" />
        </div>
        <div className="h-4 w-[90%] rounded bg-paper2 dark:bg-coal shimmer" />
        <div className="h-4 w-[60%] rounded bg-paper2 dark:bg-coal shimmer" />
        {!compact && <div className="h-5 w-20 rounded-full bg-paper2 dark:bg-coal shimmer mt-2" />}
      </div>
    </div>
  );
}
