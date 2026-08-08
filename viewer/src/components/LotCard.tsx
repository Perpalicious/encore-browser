import { useRef, type CSSProperties, type KeyboardEvent, type MouseEvent } from 'react';
import type { MobileCols } from '../lib/types';
import type { LotView } from '../lib/lotView';
import { conditionColor } from '../lib/lotView';
import { formatMoney } from '../lib/resale';
import { TITLE_H, FIGURE_ROW_H, META_ROW_H } from '../hooks/useGridGeometry';
import { useSwipeToWatch } from '../hooks/useSwipeToWatch';
import { TileImage } from './pills/TileImage';

/**
 * A lot card — docs/design/README.md § "Desktop grid".
 *
 * Hierarchy is thumb → title → condition → resale. Condition owns the colour
 * (the 2px lid plus the mono word); money is greyscale, separated by size and
 * weight rather than hue; retail is demoted to --dim3. The whole card is the
 * click target — the old per-card "Details" button is gone.
 *
 * Height is FIXED, and the virtualiser depends on that: the title clamps to two
 * lines with a min-height, and the text block is a constant TEXT_H tall. See
 * the note in LotGrid before making anything here grow.
 *
 * On a touch device the card also swipes right to watch, exactly like a list
 * row — an iPad is wider than 760px, so it gets this grid rather than the rows,
 * and the gesture has to exist where the user actually is. The swipe shell is
 * mounted ONLY on touch, so the desktop DOM is unchanged.
 */

interface Props {
  view: LotView;
  expanded: boolean;
  /** The keyboard cursor sits on this card. */
  cursor?: boolean;
  onToggleExpand: () => void;
  watched: boolean;
  onToggleWatch: () => void;
  /** Measured column width — drives tile padding at narrow widths. */
  colW: number;
  /** Mobile column count, when the mobile card stepper is driving the grid. */
  mobileCols?: MobileCols;
  /** Height of the text block, from the geometry hook. */
  textH: number;
  /** Touch-capable: the swipe gesture is live. */
  touch?: boolean;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

/** Tile padding tightens as columns narrow, per the handoff. */
function tilePadding(colW: number): number {
  if (colW < 100) return 8;
  if (colW < 150) return 11;
  return 16;
}

const figureStyle: CSSProperties = {
  fontFamily: MONO,
  fontWeight: 500,
  fontSize: '12.5px',
  lineHeight: 1,
  color: 'var(--text)',
  fontVariantNumeric: 'tabular-nums',
};

const subFigureStyle: CSSProperties = {
  fontFamily: MONO,
  fontWeight: 400,
  fontSize: '9.5px',
  lineHeight: 1,
  color: 'var(--dim3)',
  fontVariantNumeric: 'tabular-nums',
};

export function LotCard({
  view,
  expanded,
  cursor = false,
  onToggleExpand,
  watched,
  onToggleWatch,
  colW,
  mobileCols,
  textH,
  touch = false,
}: Props) {
  const cc = conditionColor(view.cond);
  // At 4-up the title can no longer carry the lot, so the photo does: the
  // figures move onto the image in a gradient plate, and the value tick is
  // suppressed to keep the tile readable. At 3-up the bucket line is dropped.
  const plate = mobileCols === 4;
  const showMeta = mobileCols === undefined || mobileCols === 2;
  const titleFs = mobileCols === 4 ? '10px' : mobileCols === 3 ? '11px' : '12.5px';
  const titleH = mobileCols === 4 ? 25 : mobileCols === 3 ? 28 : TITLE_H;
  const figFs = mobileCols === 3 ? '11.5px' : '12.5px';
  const textPad =
    mobileCols === 4 ? '5px 6px 6px' : mobileCols === 3 ? '6px 7px 7px' : '8px 9px 9px';

  const shellRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLElement>(null);
  const watchLabelRef = useRef<HTMLSpanElement>(null);

  const paint = (dx: number) => {
    if (cardRef.current) cardRef.current.style.transform = `translateX(${dx}px)`;
    if (shellRef.current) shellRef.current.style.background = dx > 0 ? 'var(--lavbg)' : '';
    if (watchLabelRef.current) watchLabelRef.current.style.opacity = dx > 0 ? '1' : '0';
  };

  const swipe = useSwipeToWatch({ enabled: touch, onPaint: paint, onCommit: onToggleWatch });

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onToggleExpand();
    }
  };

  const onStarClick = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onToggleWatch();
  };

  const card = (
    <article
      ref={cardRef}
      data-testid="lot-card"
      data-lot-number={view.lot}
      className="lot-card"
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      aria-label={expanded ? 'Hide details' : 'Show details'}
      onClick={() => {
        if (swipe.shouldSwallowClick()) return;
        onToggleExpand();
      }}
      onKeyDown={onKeyDown}
      onPointerDown={swipe.onPointerDown}
      data-expanded={expanded ? 'true' : undefined}
      data-cursor={cursor ? 'true' : undefined}
      style={
        touch
          ? {
              // Same trap as the list row: without user-select:none a
              // horizontal drag starts a text selection, the browser takes the
              // gesture, and the NEXT swipe silently does nothing.
              touchAction: 'pan-y',
              userSelect: 'none',
              WebkitUserSelect: 'none',
              height: '100%',
            }
          : undefined
      }
    >
      <div style={{ position: 'relative' }}>
        <TileImage
          src={view.img}
          alt={view.title}
          pad={tilePadding(colW)}
          tint={view.tint}
          href={view.url}
        />

        {/* Day letter — which of the two auctions this lot belongs to. */}
        <span
          aria-hidden
          style={{
            position: 'absolute',
            top: 5,
            left: 6,
            fontFamily: MONO,
            fontWeight: 700,
            fontSize: '8px',
            lineHeight: 1,
            color: 'var(--ink2)',
          }}
        >
          {view.day}
        </span>

        {/* Personal match — was a full chip row, now costs zero layout. */}
        {view.pick && (
          <span
            data-testid="personal-badge"
            title="Personal pick"
            aria-label="Personal pick"
            style={{
              position: 'absolute',
              top: 5,
              left: 20,
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--pick)',
              boxShadow: '0 0 0 2px rgba(255,255,255,.7)',
            }}
          />
        )}

        {/* Exceptional value — top-decile resale-to-retail ratio, computed once
            over the whole set at load (see lib/lotView.ts). */}
        {view.tick && !plate && (
          <span
            data-testid="value-badge"
            title="Top-decile resale-to-retail spread"
            style={{
              position: 'absolute',
              bottom: 5,
              left: 6,
              fontFamily: MONO,
              fontWeight: 700,
              fontSize: '8.5px',
              lineHeight: 1,
              letterSpacing: '.06em',
              padding: '3px 5px',
              borderRadius: 4,
              background: 'var(--pick)',
              color: '#fff',
            }}
          >
            ▲ VALUE
          </span>
        )}

        {plate && (
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 0,
              padding: '10px 5px 3px',
              background: 'linear-gradient(to top, var(--plate), var(--plate0))',
              display: 'flex',
              alignItems: 'flex-end',
              justifyContent: 'space-between',
            }}
          >
            {view.mid !== null && (
              <span
                data-testid="resale-summary"
                style={{
                  fontFamily: MONO,
                  fontWeight: 700,
                  fontSize: '10.5px',
                  lineHeight: 1,
                  color: 'var(--plink)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatMoney(view.mid)}
              </span>
            )}
            {view.retail !== null && (
              <span
                style={{
                  fontFamily: MONO,
                  fontWeight: 500,
                  fontSize: '8px',
                  lineHeight: 1,
                  color: 'var(--ink2)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatMoney(view.retail)}
              </span>
            )}
          </div>
        )}

        <button
          type="button"
          data-testid="star-btn"
          onClick={onStarClick}
          aria-pressed={watched}
          aria-label={`${watched ? 'Remove from list' : 'Add to list'}: ${view.title}`}
          style={{
            position: 'absolute',
            top: 4,
            right: 4,
            width: 26,
            height: 26,
            borderRadius: 8,
            background: 'rgba(14,12,22,.45)',
            backdropFilter: 'blur(6px)',
            WebkitBackdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '13px',
            lineHeight: 1,
            color: watched ? 'var(--star)' : 'rgba(255,255,255,.8)',
          }}
        >
          {watched ? '★' : '☆'}
        </button>
      </div>

      {/* Condition lid — the only full-width colour in the grid. */}
      <div aria-hidden style={{ height: 2, background: cc }} />

      {/* Fixed height — the virtualiser's row pitch is derived from it. */}
      <div
        style={{
          height: textH,
          padding: textPad,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          overflow: 'hidden',
        }}
      >
        <div
          className="lot-card__title"
          title={view.title}
          style={{
            flex: 'none',
            height: titleH,
            fontWeight: 600,
            fontSize: titleFs,
            lineHeight: 1.28,
            color: 'var(--text)',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {view.title}
        </div>

        {/* The figure row is dropped at 4-up — the plate on the tile carries it. */}
        {!plate && (
        <div
          style={{
            flex: 'none',
            height: FIGURE_ROW_H,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 5,
          }}
        >
          <span
            style={{
              fontFamily: MONO,
              fontWeight: 500,
              fontSize: '8.5px',
              lineHeight: 1,
              letterSpacing: '.05em',
              color: cc,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {view.cond ? view.cond.toUpperCase() : ''}
          </span>
          {view.mid !== null && (
            <span data-testid="resale-summary" style={{ ...figureStyle, fontSize: figFs }}>
              {formatMoney(view.mid)}
            </span>
          )}
        </div>
        )}

        {/* Bucket ↔ retail survives only at 2-up and on desktop. */}
        {showMeta && (
        <div
          style={{
            flex: 'none',
            height: META_ROW_H,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 6,
          }}
        >
          <span
            style={{
              fontSize: '9.5px',
              lineHeight: 1.2,
              color: 'var(--dim3)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {view.bucket ?? view.sub}
          </span>
          {view.retail !== null && <span style={subFigureStyle}>{formatMoney(view.retail)}</span>}
        </div>
        )}
      </div>
    </article>
  );

  if (!touch) return card;

  // Swipe shell — the card translates off a fixed action layer, exactly like a
  // list row. Only mounted on touch, so nothing about the desktop grid moves.
  return (
    <div
      ref={shellRef}
      style={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 11,
        height: '100%',
      }}
    >
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          padding: '0 14px',
          fontFamily: MONO,
          fontWeight: 700,
          fontSize: '9.5px',
          letterSpacing: '.1em',
        }}
      >
        <span ref={watchLabelRef} style={{ color: 'var(--lavt)', opacity: 0 }}>
          {watched ? '\u2606 REMOVE' : '\u2605 WATCH'}
        </span>
      </div>
      {card}
    </div>
  );
}
