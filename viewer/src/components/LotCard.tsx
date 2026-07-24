import { ChevronDown, ChevronUp } from 'lucide-react';
import type { Lot, Density } from '../lib/types';
import { hasResale, resaleMean, formatMoney } from '../lib/resale';
import { LotImage } from './pills/LotImage';
import { ConditionPill } from './pills/ConditionPill';
import { DayBadge } from './pills/DayBadge';
import { BatBucketPill } from './pills/BatBucketPill';
import { PersonalPickBadge } from './pills/PersonalPickBadge';
import { StarButton } from './pills/StarButton';
import { isPersonalPick } from '../lib/personal';
import { LotExpandPanel } from './LotExpandPanel';

interface Props {
  lot: Lot;
  expanded: boolean;
  onToggleExpand: () => void;
  watched: boolean;
  onToggleWatch: () => void;
  density: Density;
  inlineExpand?: boolean;
}

export function LotCard({
  lot,
  expanded,
  onToggleExpand,
  watched,
  onToggleWatch,
  density,
  inlineExpand = true,
}: Props) {
  const compact = density === 'compact';
  const aspect = compact ? 'aspect-[5/4]' : 'aspect-[4/3]';

  return (
    <article
      data-testid="lot-card"
      data-lot-number={lot.lot_number}
      className={`group relative overflow-hidden rounded-2xl bg-white dark:bg-night2
                  shadow-card dark:shadow-cardDark
                  ring-1 ring-rule/60 dark:ring-dusk
                  transition-all duration-200 hover:-translate-y-[1px] hover:shadow-cardHover
                  ${lot.is_bat ? 'ring-ember/35 dark:ring-ember/35' : ''}
                  ${watched ? 'ring-ember/60 dark:ring-ember/60' : ''}`}
    >
      {/* Bat-list left accent stripe */}
      {lot.is_bat && (
        <span
          aria-hidden
          className="absolute left-0 top-0 bottom-0 w-[3px] bg-ember/80 dark:bg-ember z-10"
        />
      )}

      {/* Star button */}
      <StarButton watched={watched} onToggle={onToggleWatch} />

      {/* Clickable body region */}
      <button
        type="button"
        onClick={onToggleExpand}
        aria-expanded={expanded}
        className="block w-full text-left"
      >
        <div className="relative">
          <LotImage src={lot.thumb_url} alt={lot.title} aspect={aspect} />
          {watched && (
            <span className="absolute bottom-2.5 left-2.5 inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] font-medium px-2 py-1 rounded-full bg-ember text-white shadow">
              Watching
            </span>
          )}
        </div>

        <div className={`px-4 ${compact ? 'pt-2.5 pb-2.5' : 'pt-3.5 pb-4'}`}>
          {/* Meta row */}
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <ConditionPill value={lot.condition} size={compact ? 'sm' : 'md'} />
            <DayBadge day={lot.day} className="text-ink2 dark:text-bone2" />
          </div>

          {/* Title */}
          <h3
            className={`font-serif ${compact ? 'text-[15px] leading-[1.25]' : 'text-[17px] leading-[1.22]'} text-ink dark:text-bone`}
            style={{
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              minHeight: compact ? '2.5em' : '2.45em',
            } as React.CSSProperties}
            title={lot.title}
          >
            {lot.title}
          </h3>

          {/* Resale / retail summary — only when this lot was valued */}
          {hasResale(lot) && (
            <div
              data-testid="resale-summary"
              className={`${compact ? 'mt-1.5' : 'mt-2'} flex items-baseline gap-2.5 ${compact ? 'text-[12px]' : 'text-[13px]'}`}
            >
              <span className="inline-flex items-baseline gap-1 font-medium text-emerald-600 dark:text-emerald-400">
                <span className="uppercase tracking-[0.08em] text-[0.72em] opacity-80">Resale</span>
                <span>~{formatMoney(resaleMean(lot))}</span>
              </span>
              {lot.est_retail_price !== null && (
                <span className="inline-flex items-baseline gap-1 font-medium text-rose-600/80 dark:text-rose-400/80">
                  <span className="uppercase tracking-[0.08em] text-[0.72em] opacity-80">Retail</span>
                  <span>{formatMoney(lot.est_retail_price)}</span>
                </span>
              )}
            </div>
          )}

          {/* Bottom row: personal pick + bat bucket + details toggle */}
          <div className={`${compact ? 'mt-2' : 'mt-3'} flex items-center gap-1.5 flex-wrap`}>
            {isPersonalPick(lot) && (
              <PersonalPickBadge
                strength={lot.match_strength}
                size={compact ? 'sm' : 'md'}
              />
            )}
            {lot.is_bat && lot.bat_buckets.length > 0 && (
              <BatBucketPill
                label={lot.bat_buckets[0]}
                extra={Math.max(0, lot.bat_buckets.length - 1)}
                size={compact ? 'sm' : 'md'}
              />
            )}
            {lot.is_bat && lot.bat_buckets.length === 0 && (
              <BatBucketPill label="Match" size={compact ? 'sm' : 'md'} />
            )}
            <span
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                onToggleExpand();
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onToggleExpand();
                }
              }}
              aria-expanded={expanded}
              aria-label={expanded ? 'Hide details' : 'Show details'}
              className={`ml-auto inline-flex items-center gap-1 rounded-full font-medium transition-colors cursor-pointer
                          ${compact ? 'h-7 px-2 text-[11px]' : 'h-8 px-2.5 text-[12px]'}
                          ${
                            expanded
                              ? 'bg-ink text-paper dark:bg-bone dark:text-night'
                              : 'bg-paper2 text-ink hover:bg-rule dark:bg-coal dark:text-bone dark:hover:bg-dusk ring-1 ring-rule/60 dark:ring-dusk'
                          }`}
            >
              <span>{expanded ? 'Hide' : 'Details'}</span>
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </span>
          </div>
        </div>
      </button>

      {/* Inline expand panel (standard mode) */}
      {inlineExpand && (
        <div className={`expand-grid ${expanded ? 'open' : ''}`}>
          <div className="expand-inner">
            <LotExpandPanel lot={lot} onCollapse={onToggleExpand} fullRow={false} />
          </div>
        </div>
      )}
    </article>
  );
}
