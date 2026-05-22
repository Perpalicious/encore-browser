// Lot card component with skeleton, broken-image, expand, watched, and density variants.

const { useState, useRef, useEffect, useMemo } = React;

// ---------- Condition pill helpers ----------
const CONDITION_STYLES = {
  'New':           'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:ring-emerald-800/60',
  'Like New':      'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:ring-emerald-800/60',
  'Good':          'bg-paper2 text-ink2 ring-rule dark:bg-coal dark:text-bone2 dark:ring-dusk',
  'Fair':          'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:ring-amber-800/60',
  'Heavily Used':  'bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-900/30 dark:text-rose-200 dark:ring-rose-800/60',
};

const ConditionPill = ({ value, size = 'md', className = '' }) => {
  const sz = size === 'sm' ? 'text-[10px] px-1.5 py-[2px]' : 'text-[11px] px-2 py-[3px]';
  return (
    <span className={`inline-flex items-center font-medium tracking-wide uppercase rounded-full ring-1 ${sz} ${CONDITION_STYLES[value]} ${className}`}>
      {value}
    </span>
  );
};

// ---------- Image with broken-fallback + loading shimmer ----------
const LotImage = ({ src, alt, aspect = 'aspect-[4/3]', className = '' }) => {
  const [state, setState] = useState(src ? 'loading' : 'broken');
  // If src changes, reset
  useEffect(() => { setState(src ? 'loading' : 'broken'); }, [src]);

  return (
    <div className={`relative ${aspect} w-full overflow-hidden bg-paper2 dark:bg-coal ${className}`}>
      {state === 'broken' ? (
        <div className="absolute inset-0 grid place-items-center bg-paper2 dark:bg-coal">
          <div className="flex flex-col items-center gap-1.5 text-ink2/70 dark:text-bone2/70">
            <ImageOff size={28} strokeWidth={1.5} />
            <span className="text-[10px] uppercase tracking-[0.14em] font-mono">no image</span>
          </div>
        </div>
      ) : (
        <>
          {state === 'loading' && (
            <div className="absolute inset-0 shimmer bg-paper2 dark:bg-coal" />
          )}
          <img
            src={src}
            alt={alt}
            loading="lazy"
            onLoad={() => setState('loaded')}
            onError={() => setState('broken')}
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${state === 'loaded' ? 'opacity-100' : 'opacity-0'}`}
            draggable="false"
          />
        </>
      )}
    </div>
  );
};

// ---------- Star button (top-right of card) ----------
const StarButton = ({ watched, onToggle }) => (
  <button
    type="button"
    onClick={(e) => { e.stopPropagation(); onToggle(); }}
    aria-label={watched ? 'Remove from watched' : 'Add to watched'}
    aria-pressed={watched}
    className={`absolute top-2.5 right-2.5 z-10 h-11 w-11 grid place-items-center rounded-full
                backdrop-blur-md transition-all
                ${watched
                  ? 'bg-ember text-white shadow-pop hover:bg-ember2'
                  : 'bg-white/85 text-ink/80 hover:bg-white hover:text-ember shadow ring-1 ring-black/5 dark:bg-night2/85 dark:text-bone/80 dark:ring-white/10 dark:hover:text-ember'}`}
  >
    <Star filled={watched} size={20} strokeWidth={2} />
  </button>
);

// ---------- Day badge ----------
const DayBadge = ({ day, className = '' }) => (
  <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] font-medium ${className}`}>
    <span className={`h-1.5 w-1.5 rounded-full ${day === 'Sunday' ? 'bg-ember' : 'bg-indigo-500 dark:bg-indigo-400'}`} />
    {day}
  </span>
);

// ---------- Bat bucket pill ----------
const BatBucketPill = ({ label, extra = 0, subtle = false, size = 'md' }) => {
  const sz = size === 'sm' ? 'text-[10px] px-1.5 py-[2px]' : 'text-[11px] px-2 py-[3px]';
  const star = size === 'sm' ? 10 : 11;
  return (
    <span className={`inline-flex items-center gap-1 font-medium rounded-full ${sz}
                    ${subtle
                      ? 'bg-paper2 text-ink2 ring-1 ring-rule dark:bg-coal dark:text-bone2 dark:ring-dusk'
                      : 'bg-ember/10 text-ember2 ring-1 ring-ember/20 dark:bg-ember/15 dark:text-ember dark:ring-ember/30'}`}>
      <Sparkle size={star} strokeWidth={2} />
      <span>{label}</span>
      {extra > 0 && <span className="opacity-70">+{extra}</span>}
    </span>
  );
};

// ---------- Expand panel (used both in-card for standard, and as a full-row sibling for compact) ----------
const LotExpandPanel = ({ lot, onCollapse, fullRow = false }) => (
  <div className={`${fullRow
    ? 'col-span-full rounded-2xl bg-white dark:bg-night2 ring-1 ring-rule/60 dark:ring-dusk shadow-card dark:shadow-cardDark overflow-hidden animate-fadeIn relative'
    : ''}`}
  >
    {fullRow && lot.is_bat && (
      <span aria-hidden className="absolute left-0 top-0 bottom-0 w-[3px] bg-ember/80 dark:bg-ember" />
    )}
    <div className={`${fullRow ? 'p-5 md:p-6 grid gap-5 md:gap-7 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]' : 'px-4 pb-4 border-t border-rule dark:border-dusk pt-4'}`}>
      <div>
        <LotImage
          src={lot.image_url || lot.thumb_url}
          alt={lot.title}
          aspect={fullRow ? 'aspect-[4/3]' : 'aspect-[4/3]'}
          className="rounded-xl ring-1 ring-rule/60 dark:ring-dusk"
        />
      </div>
      <div className="min-w-0">
        {/* Header — title, lot #, day, condition */}
        <div className="flex items-start justify-between gap-3">
          <h3 className={`font-serif text-ink dark:text-bone ${fullRow ? 'text-[22px] md:text-[26px] leading-[1.15]' : 'text-[18px] leading-[1.2]'}`}>
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
          <DayBadge day={lot.day} className="text-ink2 dark:text-bone2 px-2 py-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk" />
          <span className="font-mono text-[11px] tracking-wide text-ink2 dark:text-bone2 px-2 py-[3px] rounded-full bg-paper2 dark:bg-coal ring-1 ring-rule dark:ring-dusk uppercase">Lot {lot.lot_number}</span>
        </div>

        {lot.description ? (
          <p className="mt-4 text-[14.5px] leading-[1.6] text-ink2 dark:text-bone2 font-sans">
            {lot.description}
          </p>
        ) : (
          <p className="mt-4 text-[13px] italic text-ink2/60 dark:text-bone2/60">No description provided.</p>
        )}

        <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-5 gap-y-2 text-[12px]">
          <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">Category</dt>
          <dd className="text-ink dark:text-bone">{lot.category}</dd>
          <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">Sub</dt>
          <dd className="text-ink dark:text-bone">{lot.subcategory}</dd>
          {lot.is_bat && lot.bat_buckets.length > 0 && (
            <React.Fragment>
              <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">Buckets</dt>
              <dd className="flex flex-wrap gap-1.5">
                {lot.bat_buckets.map((b) => (
                  <span key={b} className="inline-flex items-center text-[11px] font-medium px-2 py-[2px] rounded-full bg-ember/10 text-ember2 ring-1 ring-ember/20 dark:bg-ember/15 dark:text-ember dark:ring-ember/30">{b}</span>
                ))}
              </dd>
            </React.Fragment>
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

// ---------- The card ----------
const LotCard = ({ lot, expanded, onToggleExpand, watched, onToggleWatch, density, inlineExpand = true }) => {
  const compact = density === 'compact';
  const aspect = compact ? 'aspect-[5/4]' : 'aspect-[4/3]';

  return (
    <article
      data-screen-label={`Lot ${lot.lot_number}`}
      className={`group relative overflow-hidden rounded-2xl bg-white dark:bg-night2
                  shadow-card dark:shadow-cardDark
                  ring-1 ring-rule/60 dark:ring-dusk
                  transition-all duration-200 hover:-translate-y-[1px] hover:shadow-cardHover
                  ${lot.is_bat ? 'ring-ember/35 dark:ring-ember/35' : ''}
                  ${watched ? 'ring-ember/60 dark:ring-ember/60' : ''}`}
    >
      {/* Bat-list left accent stripe (subtle) */}
      {lot.is_bat && (
        <span aria-hidden className="absolute left-0 top-0 bottom-0 w-[3px] bg-ember/80 dark:bg-ember" />
      )}

      {/* Star button — pinned to card root (outside the body button) so we don't nest <button>s */}
      <StarButton watched={watched} onToggle={onToggleWatch} />

      {/* Clickable body region (image + meta) */}
      <button
        type="button"
        onClick={onToggleExpand}
        aria-expanded={expanded}
        className="block w-full text-left"
      >
        <div className="relative">
          <LotImage src={lot.thumb_url} alt={lot.title} aspect={aspect} />
          {/* Watched indicator: small ember pill pinned bottom-left of image */}
          {watched && (
            <span className="absolute bottom-2.5 left-2.5 inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] font-medium px-2 py-1 rounded-full bg-ember text-white shadow">
              Watching
            </span>
          )}
        </div>

        <div className={`px-4 ${compact ? 'pt-2.5 pb-2.5' : 'pt-3.5 pb-4'}`}>
          {/* meta row: condition + day (lot # moved to expanded details) */}
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <ConditionPill value={lot.condition} size={compact ? 'sm' : 'md'} />
            <DayBadge day={lot.day} className="text-ink2 dark:text-bone2" />
          </div>

          {/* title — 2 line clamp, fixed height */}
          <h3
            className={`font-serif ${compact ? 'text-[15px] leading-[1.25]' : 'text-[17px] leading-[1.22]'} text-ink dark:text-bone`}
            style={{
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              minHeight: compact ? '2.5em' : '2.45em',
            }}
            title={lot.title}
          >
            {lot.title}
          </h3>

          {/* bottom row: bat bucket + visible expand toggle */}
          <div className={`${compact ? 'mt-2' : 'mt-3'} flex items-center gap-1.5 flex-wrap`}>
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
              onClick={(e) => { e.stopPropagation(); e.preventDefault(); onToggleExpand(); }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggleExpand(); } }}
              aria-expanded={expanded}
              aria-label={expanded ? 'Hide details' : 'Show details'}
              className={`ml-auto inline-flex items-center gap-1 rounded-full font-medium transition-colors cursor-pointer
                          ${compact ? 'h-7 px-2 text-[11px]' : 'h-8 px-2.5 text-[12px]'}
                          ${expanded
                            ? 'bg-ink text-paper dark:bg-bone dark:text-night'
                            : 'bg-paper2 text-ink hover:bg-rule dark:bg-coal dark:text-bone dark:hover:bg-dusk ring-1 ring-rule/60 dark:ring-dusk'}`}
            >
              <span>{expanded ? 'Hide' : 'Details'}</span>
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </span>
          </div>
        </div>
      </button>

      {/* Expanded panel — grid-template-rows animation trick (inline mode only) */}
      {inlineExpand && (
      <div className={`expand-grid ${expanded ? 'open' : ''}`}>
        <div className="expand-inner">
          <div className="px-4 pb-4 border-t border-rule dark:border-dusk pt-4">
            <LotImage
              src={lot.image_url || lot.thumb_url}
              alt={lot.title}
              aspect="aspect-[4/3]"
              className="rounded-xl ring-1 ring-rule/60 dark:ring-dusk"
            />

            {/* Compact-mode: show condition only when expanded */}
            {compact && (
              <div className="mt-3">
                <ConditionPill value={lot.condition} />
              </div>
            )}

            {lot.description ? (
              <p className="mt-4 text-[14px] leading-[1.55] text-ink2 dark:text-bone2 font-sans">
                {lot.description}
              </p>
            ) : (
              <p className="mt-4 text-[13px] italic text-ink2/60 dark:text-bone2/60">No description provided.</p>
            )}

            <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12px]">
              <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">Category</dt>
              <dd className="text-ink dark:text-bone">{lot.category}</dd>
              <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">Sub</dt>
              <dd className="text-ink dark:text-bone">{lot.subcategory}</dd>
              {lot.is_bat && lot.bat_buckets.length > 0 && (
                <>
                  <dt className="uppercase tracking-[0.14em] font-mono text-ink2/70 dark:text-bone2/70">Buckets</dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {lot.bat_buckets.map((b) => (
                      <span key={b} className="inline-flex items-center text-[11px] font-medium px-2 py-[2px] rounded-full bg-ember/10 text-ember2 ring-1 ring-ember/20 dark:bg-ember/15 dark:text-ember dark:ring-ember/30">{b}</span>
                    ))}
                  </dd>
                </>
              )}
            </dl>

            <div className="mt-5 flex items-center gap-2">
              <a
                href={lot.lot_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="inline-flex items-center justify-center gap-2 h-11 px-4 rounded-full bg-ember hover:bg-ember2 active:bg-ember2 text-white font-medium text-[14px] tracking-tight shadow-sm transition-colors"
              >
                <span>View on Encore</span>
                <ExternalLink size={16} strokeWidth={2} />
              </a>
              <button
                type="button"
                onClick={onToggleExpand}
                className="inline-flex items-center justify-center gap-1.5 h-11 px-3 rounded-full text-ink2 dark:text-bone2 hover:bg-paper2 dark:hover:bg-coal text-[14px] font-medium"
              >
                <ChevronUp size={16} />
                <span>Collapse</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      )}
    </article>
  );
};

// ---------- Skeleton card ----------
const SkeletonCard = ({ density }) => {
  const compact = density === 'compact';
  return (
    <div className="rounded-2xl bg-white dark:bg-night2 ring-1 ring-rule/60 dark:ring-dusk overflow-hidden shadow-card dark:shadow-cardDark">
      <div className={`${compact ? 'aspect-[5/4]' : 'aspect-[4/3]'} bg-paper2 dark:bg-coal shimmer`} />
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
};

Object.assign(window, {
  LotCard, SkeletonCard, ConditionPill, LotImage, StarButton, DayBadge, BatBucketPill, LotExpandPanel,
});
