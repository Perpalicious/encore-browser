import { useRef, type CSSProperties, type PointerEvent } from 'react';
import type { LotView } from '../lib/lotView';
import { conditionColor } from '../lib/lotView';
import { formatMoney } from '../lib/resale';
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
 * opaque or the action shows through before you've swiped.
 *
 * There is exactly ONE swipe, and it is rightward: add to / remove from the
 * list. A left swipe is deliberately inert — the row will not even follow your
 * thumb that way, so nothing suggests an action is hiding over there. Removing
 * lots from the results on a flick was too destructive for a gesture this easy
 * to make by accident while scrolling.
 */

interface Props {
  view: LotView;
  mobile: boolean;
  coarse: boolean;
  height: number;
  watched: boolean;
  cursor: boolean;
  onOpen: () => void;
  onToggleWatch: () => void;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

/** Past this many px the gesture commits on release. */
const SWIPE_THRESHOLD = 70;
const SWIPE_MAX = 140;

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
  height,
  watched,
  cursor,
  onOpen,
  onToggleWatch,
}: Props) {
  const swipe = useRef({ startX: 0, dx: 0, active: false, moved: false });
  /**
   * A pointer down/move/up on the row also produces a click, so any DRAG would
   * otherwise open the detail overlay when you let go — the swipe you just
   * committed, a left drag that intentionally does nothing, a flick that
   * scrolled the list.
   *
   * Held as a deadline rather than a boolean: a boolean is only cleared by the
   * click that follows, and on touch that click does not always arrive, which
   * leaves the flag set and eats your NEXT tap. A deadline expires on its own.
   */
  const swallowClicksUntil = useRef(0);
  const SWALLOW_MS = 400;
  const shellRef = useRef<HTMLDivElement>(null);
  const rowRef = useRef<HTMLDivElement>(null);
  const watchLabelRef = useRef<HTMLSpanElement>(null);
  const cc = conditionColor(view.cond);
  const thumb = mobile ? 58 : 52;
  const starSize = coarse ? 44 : 34;

  /**
   * The drag is driven IMPERATIVELY: window listeners for the life of the
   * gesture, and the transform written straight to the DOM node.
   *
   * Re-rendering the row on every frame is what broke this. React re-creating
   * the row's element mid-drag makes Chromium fire `pointercancel` — the
   * gesture died one frame in, snapped back, and committed nothing. Not
   * touching React state until the gesture ends removes the whole class of
   * problem, and drops a render per frame while dragging.
   */
  const paint = (dx: number) => {
    const row = rowRef.current;
    const shell = shellRef.current;
    if (!row || !shell) return;
    row.style.transform = `translateX(${dx}px)`;
    shell.style.background = dx > 0 ? 'var(--lavbg)' : cursor ? 'var(--lavbg)' : 'var(--bg)';
    if (watchLabelRef.current) watchLabelRef.current.style.opacity = dx > 0 ? '1' : '0';
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (!coarse) return;
    const startX = e.clientX;
    const startY = e.clientY;
    swipe.current = { startX, dx: 0, active: false, moved: false };

    const onMove = (ev: globalThis.PointerEvent) => {
      const dxRaw = ev.clientX - startX;
      const dyRaw = ev.clientY - startY;
      // Anything past tap slop, in any direction, is a drag and not a tap.
      if (Math.abs(dxRaw) > 10 || Math.abs(dyRaw) > 10) swipe.current.moved = true;
      // Let a vertical drag scroll the list; only claim the gesture once it is
      // clearly horizontal. touch-action: pan-y keeps scrolling working meanwhile.
      // Rightward only: a leftward drag never claims the gesture, so the list
      // keeps scrolling under it and the row stays put.
      if (!swipe.current.active) {
        if (dxRaw < 10 || dxRaw <= Math.abs(dyRaw)) return;
        swipe.current.active = true;
      }
      const next = Math.max(0, Math.min(SWIPE_MAX, dxRaw));
      swipe.current.dx = next;
      paint(next);
    };

    const onEnd = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onEnd);
      window.removeEventListener('pointercancel', onEnd);
      const { active, moved, dx: committed } = swipe.current;
      swipe.current = { startX: 0, dx: 0, active: false, moved: false };
      paint(0);
      if (moved) swallowClicksUntil.current = performance.now() + SWALLOW_MS;
      if (!active) return;
      if (committed > SWIPE_THRESHOLD) onToggleWatch();
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onEnd);
    window.addEventListener('pointercancel', onEnd);
  };

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
          if (performance.now() < swallowClicksUntil.current) return;
          onOpen();
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onOpen();
          }
        }}
        onPointerDown={onPointerDown}
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
          touchAction: 'pan-y',
          // Only where swipe is live. A horizontal drag across a row otherwise
          // starts a native text selection, and the browser then treats the
          // whole thing as a selection gesture — pointermove stops reaching us
          // and the NEXT swipe silently does nothing. Desktop keeps selectable
          // text, since nothing there drags.
          userSelect: coarse ? 'none' : undefined,
          WebkitUserSelect: coarse ? 'none' : undefined,
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
          <TileImage src={view.img} alt={view.title} pad={4} tint={view.tint} />
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
                {view.tick && <ValueTick />}
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
              {view.retail !== null && (
                <span style={{ ...microFigure, fontSize: '10px', color: 'var(--dim3)' }}>
                  {formatMoney(view.retail)}
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
                  fontSize: '10px',
                  color: 'var(--dim3)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {view.bucket ?? view.sub}
              </div>
            </div>
            <div style={{ width: 110, flex: 'none' }}>
              <ConditionDot cc={cc} cond={view.cond} />
            </div>
            <div style={{ width: 52, flex: 'none' }}>{view.tick && <ValueTick />}</div>
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
            <div style={{ width: 66, flex: 'none', textAlign: 'right' }}>
              {view.retail !== null && (
                <span style={{ ...microFigure, fontSize: '11px', color: 'var(--dim3)' }}>
                  {formatMoney(view.retail)}
                </span>
              )}
            </div>
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

function ValueTick() {
  return (
    <span
      data-testid="value-badge"
      title="Top-decile resale-to-retail spread"
      style={{
        fontFamily: MONO,
        fontWeight: 700,
        fontSize: '8.5px',
        lineHeight: 1,
        letterSpacing: '.06em',
        padding: '3px 5px',
        borderRadius: 20,
        background: 'var(--pick)',
        color: '#fff',
      }}
    >
      ▲
    </span>
  );
}
