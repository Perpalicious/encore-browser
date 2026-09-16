import { useRef, type CSSProperties } from 'react';
import type { HammerWeek } from '../lib/types';
import type { LotView } from '../lib/lotView';
import { conditionColor, closeLabel } from '../lib/lotView';
import { formatMoney } from '../lib/resale';
import { hammerLine } from '../lib/hammer';
import { useSwipeToWatch } from '../hooks/useSwipeToWatch';
import { TileImage } from './pills/TileImage';

/**
 * One lot as a row — docs/design/README.md § "Desktop list view" and
 * § "Mobile / Rows mode".
 *
 * Both variants are the same component: the desktop list is a wide row of
 * fixed columns, mobile stacks title over a meta line with the figures
 * right-aligned. What actually differs between them is density, not structure.
 *
 * Swipe is enabled by INPUT, not width — a touch-capable desktop gets it too.
 * The row translates over a fixed action layer, so the row background must stay
 * opaque or the action shows through before you've swiped. The gesture itself
 * lives in useSwipeToWatch, shared with the grid card.
 */

interface Props {
  view: LotView;
  mobile: boolean;
  /** Coarse pointer: taller rows, bigger hit areas. */
  coarse: boolean;
  /** Touch-capable: the swipe gesture is live. */
  touch: boolean;
  height: number;
  watched: boolean;
  cursor: boolean;
  onOpen: () => void;
  onToggleWatch: () => void;
  /** Clock for the ENDED state; undefined when the bundle carries no times. */
  now?: number;
  /** Past sale history for this product, newest week first; null when none. */
  hammer?: HammerWeek[] | null;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

const microFigure: CSSProperties = {
  fontFamily: MONO,
  fontWeight: 500,
  fontVariantNumeric: 'tabular-nums',
  lineHeight: 1,
};

export function LotRow({
  view,
  mobile,
  coarse,
  touch,
  height,
  watched,
  cursor,
  onOpen,
  onToggleWatch,
  now,
  hammer,
}: Props) {
  const shellRef = useRef<HTMLDivElement>(null);
  const rowRef = useRef<HTMLDivElement>(null);
  const watchLabelRef = useRef<HTMLSpanElement>(null);
  const cc = conditionColor(view.cond);
  const ended = now !== undefined && view.closeMs !== null && view.closeMs <= now;
  const thumb = mobile ? 58 : 52;
  const starSize = coarse ? 44 : 34;
  // The wide desktop row can carry the whole line beside the bucket; the 78px
  // mobile row gets the short form under the resale figure, where there is a
  // spare line and no competition for width.
  const week = hammer && hammer.length > 0 ? hammer[0] : null;
  const hammerText = week ? hammerLine(week, mobile ? 'minimal' : 'full') : null;

  const paint = (dx: number) => {
    const row = rowRef.current;
    const shell = shellRef.current;
    if (!row || !shell) return;
    row.style.transform = `translateX(${dx}px)`;
    shell.style.background = dx > 0 ? 'var(--lavbg)' : cursor ? 'var(--lavbg)' : 'var(--bg)';
    if (watchLabelRef.current) watchLabelRef.current.style.opacity = dx > 0 ? '1' : '0';
  };

  const swipe = useSwipeToWatch({ enabled: touch, onPaint: paint, onCommit: onToggleWatch });

  const rowBackground = cursor ? 'var(--lavbg)' : 'var(--bg)';

  return (
    <div
      ref={shellRef}
      style={{
        position: 'relative',
        overflow: 'hidden',
        height,
        background: rowBackground,
        borderBottom: '1px solid var(--line2)',
      }}
    >
      {/* Action layer, revealed as the row translates off it. */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          fontFamily: MONO,
          fontWeight: 700,
          fontSize: '10px',
          letterSpacing: '.1em',
        }}
      >
        <span ref={watchLabelRef} style={{ color: 'var(--lavt)', opacity: 0 }}>
          {watched ? '☆ REMOVE' : '★ WATCH'}
        </span>
      </div>

      <div
        ref={rowRef}
        data-testid="lot-row"
        data-lot-number={view.lot}
        role="button"
        tabIndex={0}
        aria-label="Show details"
        data-cursor={cursor ? 'true' : undefined}
        onClick={() => {
          if (swipe.shouldSwallowClick()) return;
          onOpen();
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onOpen();
          }
        }}
        onPointerDown={swipe.onPointerDown}
        className="lot-row"
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          gap: mobile ? 11 : 10,
          height: '100%',
          padding: mobile ? '9px 13px' : coarse ? '11px 12px' : '7px 10px',
          cursor: 'pointer',
          background: rowBackground,
          opacity: ended ? 0.55 : undefined,
          touchAction: 'pan-y',
          // Only where swipe is live. A horizontal drag across a row otherwise
          // starts a native text selection, and the browser then treats the
          // whole thing as a selection gesture — pointermove stops reaching us
          // and the NEXT swipe silently does nothing. Desktop keeps selectable
          // text, since nothing there drags.
          userSelect: touch ? 'none' : undefined,
          WebkitUserSelect: touch ? 'none' : undefined,
        }}
      >
        <div
          style={{
            width: thumb,
            height: thumb,
            flex: 'none',
            borderRadius: 8,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <TileImage src={view.img} alt={view.title} pad={4} tint={view.tint} href={view.url} />
          {view.pick && (
            <span
              data-testid="personal-badge"
              title="Personal pick"
              aria-label="Personal pick"
              style={{
                position: 'absolute',
                top: 3,
                left: 3,
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--pick)',
                boxShadow: '0 0 0 2px rgba(255,255,255,.7)',
              }}
            />
          )}
        </div>

        {mobile ? (
          <>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div
                className="lot-card__title"
                style={{
                  fontWeight: 600,
                  fontSize: '13.5px',
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
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                <ConditionDot cc={cc} cond={view.cond} />
                <span style={{ ...microFigure, fontSize: '9px', color: 'var(--dim3)' }}>
                  {view.lot}
                </span>
                {view.closeMs !== null && (
                  <span
                    data-testid="close-time"
                    style={{
                      ...microFigure,
                      fontSize: '9px',
                      color: ended ? 'var(--c-heavy)' : 'var(--dim3)',
                    }}
                  >
                    {ended ? 'ENDED' : closeLabel(view.closeMs)}
                  </span>
                )}
              </div>
            </div>
            <div
              style={{
                flex: 'none',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: 4,
              }}
            >
              {view.mid !== null && (
                <span
                  data-testid="resale-summary"
                  style={{ ...microFigure, fontSize: '13.5px', color: 'var(--text)' }}
                >
                  {formatMoney(view.mid)}
                </span>
              )}
              {hammerText && (
                <span
                  data-testid="hammer-line"
                  title="What this product sold for last time"
                  style={{ ...microFigure, fontSize: '9px', color: 'var(--dim3)' }}
                >
                  {hammerText}
                </span>
              )}
            </div>
          </>
        ) : (
          <>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: '13px',
                  lineHeight: 1.25,
                  color: 'var(--text)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {view.title}
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  minWidth: 0,
                  fontSize: '10px',
                  color: 'var(--dim3)',
                }}
              >
                <span
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {view.bucket ?? view.sub}
                </span>
                {hammerText && (
                  <span
                    data-testid="hammer-line"
                    title="What this product sold for last time"
                    style={{
                      ...microFigure,
                      flex: 'none',
                      fontSize: '9.5px',
                      color: 'var(--dim3)',
                    }}
                  >
                    {hammerText}
                  </span>
                )}
              </div>
            </div>
            <div style={{ width: 110, flex: 'none' }}>
              <ConditionDot cc={cc} cond={view.cond} />
            </div>
            <div style={{ width: 78, flex: 'none', textAlign: 'right' }}>
              {view.mid !== null && (
                <span
                  data-testid="resale-summary"
                  style={{ ...microFigure, fontSize: '13px', color: 'var(--text)' }}
                >
                  {formatMoney(view.mid)}
                </span>
              )}
            </div>
            {view.closeMs !== null && (
              <div
                data-testid="close-time"
                style={{
                  width: 52,
                  flex: 'none',
                  textAlign: 'right',
                  ...microFigure,
                  fontSize: '10px',
                  color: ended ? 'var(--c-heavy)' : 'var(--dim3)',
                }}
              >
                {ended ? 'ENDED' : closeLabel(view.closeMs)}
              </div>
            )}
            <div
              style={{
                width: 56,
                flex: 'none',
                textAlign: 'right',
                ...microFigure,
                fontSize: '10px',
                color: 'var(--dim3)',
              }}
            >
              {view.lot}
            </div>
          </>
        )}

        <button
          type="button"
          data-testid="star-btn"
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
            onToggleWatch();
          }}
          aria-pressed={watched}
          aria-label={`${watched ? 'Remove from list' : 'Add to list'}: ${view.title}`}
          style={{
            width: mobile ? 26 : starSize,
            height: mobile ? 26 : starSize,
            flex: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 8,
            fontSize: coarse ? '16px' : '13px',
            color: watched ? 'var(--star2)' : 'var(--dim3)',
          }}
        >
          {watched ? '★' : '☆'}
        </button>
      </div>
    </div>
  );
}

function ConditionDot({ cc, cond }: { cc: string; cond: string | null }) {
  if (!cond) return null;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontFamily: MONO,
        fontWeight: 500,
        fontSize: '9px',
        letterSpacing: '.05em',
        color: cc,
        whiteSpace: 'nowrap',
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: cc, flex: 'none' }} />
      {cond.toUpperCase()}
    </span>
  );
}
