import { X, ExternalLink, ChevronUp } from 'lucide-react';
import type { Lot } from '../lib/types';
import { LotImage } from './pills/LotImage';
import { ConditionPill } from './pills/ConditionPill';
import { DayBadge } from './pills/DayBadge';

interface Props {
  lot: Lot;
  onCollapse: () => void;
  fullRow?: boolean;
}

export function LotExpandPanel({ lot, onCollapse, fullRow = false }: Props) {
  return (
    <div
      className={
        fullRow
          ? 'col-span-full rounded-2xl bg-white dark:bg-night2 ring-1 ring-rule/60 dark:ring-dusk shadow-card dark:shadow-cardDark overflow-hidden animate-fadeIn relative'
          : ''
      }
    >
      {fullRow && lot.is_bat && (
        <span
          aria-hidden
          className="absolute left-0 top-0 bottom-0 w-[3px] bg-ember/80 dark:bg-ember"
        />
      )}
      <div
        className={
          fullRow
            ? 'p-5 md:p-6 grid gap-5 md:gap-7 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]'
            : 'px-4 pb-4 border-t border-rule dark:border-dusk pt-4'
        }
      >
        <div>
          <LotImage
            src={lot.image_url || lot.thumb_url}
            alt={lot.title}
            aspect="aspect-[4/3]"
            className="rounded-xl ring-1 ring-rule/60 dark:ring-dusk"
          />
        </div>
        <div className="min-w-0">
          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <h3
              className={`font-serif text-ink dark:text-bone ${
                fullRow ? 'text-[22px] md:text-[26px] leading-[1.15]' : 'text-[18px] leading-[1.2]'
              }`}
            >
              {lot.title}
            </h3>
            {fullRow && (
              <button
                type="button"
                onClick={onCollapse}
                aria-label="Collapse details"
                className="shrink-0 h-9 w-9 grid place-items-center rounded-full bg-paper2 hover:bg-rule dark:bg-coal dark:hover:bg-dusk text-ink2 dark:text-bone2"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <ConditionPill value={lot.condition} />
            <DayBadge
              day={lot.day}
              className="text-ink2 dark:text-bone2 px-2 py-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk"
            />
            <span className="font-mono text-[11px] tracking-wide text-ink2 dark:text-bone2 px-2 py-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk uppercase">
              Lot {lot.lot_number}
            </span>
          </div>

          {lot.description ? (
            <p className="mt-4 text-[14.5px] leading-[1.6] text-ink2 dark:text-bone2 font-sans">
              {lot.description}
            </p>
          ) : (
            <p className="mt-4 text-[13px] italic text-ink2/60 dark:text-bone2/60">
              No description provided.
            </p>
          )}

          <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-5 gap-y-2 text-[12px]">
            <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">
              Category
            </dt>
            <dd className="text-ink dark:text-bone">{lot.category}</dd>
            <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">
              Sub
            </dt>
            <dd className="text-ink dark:text-bone">{lot.subcategory || '—'}</dd>
            {lot.is_bat && lot.bat_buckets.length > 0 && (
              <>
                <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">
                  Buckets
                </dt>
                <dd className="flex flex-wrap gap-1.5">
                  {lot.bat_buckets.map((b) => (
                    <span
                      key={b}
                      className="inline-flex items-center text-[11px] font-medium px-2 py-[2px] rounded-full bg-ember/10 text-ember2 ring-1 ring-ember/20 dark:bg-ember/15 dark:text-ember dark:ring-ember/30"
                    >
                      {b}
                    </span>
                  ))}
                </dd>
              </>
            )}
            {lot.is_nice_pick && lot.nice_pick_reason && (
              <>
                <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">
                  Pick Reason
                </dt>
                <dd className="text-ink dark:text-bone">{lot.nice_pick_reason}</dd>
              </>
            )}
          </dl>

          <div className="mt-6 flex items-center gap-2 flex-wrap">
            <a
              href={lot.lot_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center justify-center gap-2 h-11 px-5 rounded-full bg-ember hover:bg-ember2 active:bg-ember2 text-white font-medium text-[14px] tracking-tight shadow-sm transition-colors"
            >
              <span>View on Encore</span>
              <ExternalLink size={16} strokeWidth={2} />
            </a>
            <button
              type="button"
              onClick={onCollapse}
              className="inline-flex items-center justify-center gap-1.5 h-11 px-4 rounded-full text-ink2 dark:text-bone2 hover:bg-paper2 dark:hover:bg-coal text-[14px] font-medium"
            >
              <ChevronUp size={16} />
              <span>Collapse</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
