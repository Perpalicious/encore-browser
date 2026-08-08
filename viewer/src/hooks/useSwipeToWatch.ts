import { useRef, type PointerEvent } from 'react';

/**
 * Swipe-right-to-watch, shared by list rows and grid cards.
 *
 * There is exactly ONE swipe and it is rightward: add to / remove from the
 * list. A left drag is deliberately inert — the element will not even follow
 * your thumb that way, so nothing suggests an action is hiding over there.
 * Removing lots from the results on a flick was too destructive for a gesture
 * this easy to make by accident while scrolling.
 *
 * Every awkward-looking detail here is a bug that was already paid for once:
 *
 *  - The drag is driven IMPERATIVELY — window listeners for the life of the
 *    gesture, and the transform written straight to the DOM node. Re-rendering
 *    on every frame is what broke this originally: React re-creating the
 *    element mid-drag makes Chromium fire `pointercancel`, so the gesture died
 *    one frame in, snapped back, and committed nothing.
 *  - Clicks are swallowed after ANY drag past tap slop, in any direction,
 *    because a pointer down/move/up also produces a click — otherwise letting
 *    go of a swipe opens the detail overlay on top of the triage you just did.
 *  - The swallow is a DEADLINE, not a boolean. A boolean is only cleared by the
 *    click that follows it, and on touch that click does not always arrive,
 *    which leaves the flag set and eats your next tap.
 *
 * Callers must also set `touch-action: pan-y` and `user-select: none` on the
 * dragged element. Without the latter, a horizontal drag starts a native text
 * selection, the browser takes the gesture, pointermove stops arriving, and the
 * NEXT swipe silently does nothing.
 */

/** Past this many px the gesture commits on release. */
export const SWIPE_THRESHOLD = 70;
/** The element stops following your thumb here. */
export const SWIPE_MAX = 140;
/** Drag past this, in any direction, and it is not a tap. */
const TAP_SLOP = 10;
/** How long a committed drag suppresses the click it generated. */
const SWALLOW_MS = 400;

interface Options {
  /** False on a mouse-only device: no listeners are attached at all. */
  enabled: boolean;
  /** Write the offset to the DOM. Called on every frame and with 0 on release. */
  onPaint: (dx: number) => void;
  /** Fired once, on release past the threshold. */
  onCommit: () => void;
}

export interface SwipeHandlers {
  onPointerDown: (e: PointerEvent<HTMLElement>) => void;
  /** True while a click should be treated as the tail of a drag. */
  shouldSwallowClick: () => boolean;
}

export function useSwipeToWatch({ enabled, onPaint, onCommit }: Options): SwipeHandlers {
  const swipe = useRef({ dx: 0, active: false, moved: false });
  const swallowUntil = useRef(0);

  const onPointerDown = (e: PointerEvent<HTMLElement>) => {
    if (!enabled) return;
    const startX = e.clientX;
    const startY = e.clientY;
    swipe.current = { dx: 0, active: false, moved: false };

    const onMove = (ev: globalThis.PointerEvent) => {
      const dxRaw = ev.clientX - startX;
      const dyRaw = ev.clientY - startY;
      // Anything past tap slop, in any direction, is a drag and not a tap.
      if (Math.abs(dxRaw) > TAP_SLOP || Math.abs(dyRaw) > TAP_SLOP) swipe.current.moved = true;
      // Let a vertical drag scroll the list; only claim the gesture once it is
      // clearly horizontal. Rightward only, so a leftward drag never claims it.
      if (!swipe.current.active) {
        if (dxRaw < TAP_SLOP || dxRaw <= Math.abs(dyRaw)) return;
        swipe.current.active = true;
      }
      const next = Math.max(0, Math.min(SWIPE_MAX, dxRaw));
      swipe.current.dx = next;
      onPaint(next);
    };

    const onEnd = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onEnd);
      window.removeEventListener('pointercancel', onEnd);
      const { active, moved, dx: committed } = swipe.current;
      swipe.current = { dx: 0, active: false, moved: false };
      onPaint(0);
      if (moved) swallowUntil.current = performance.now() + SWALLOW_MS;
      if (!active) return;
      if (committed > SWIPE_THRESHOLD) onCommit();
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onEnd);
    window.addEventListener('pointercancel', onEnd);
  };

  return {
    onPointerDown,
    shouldSwallowClick: () => performance.now() < swallowUntil.current,
  };
}
