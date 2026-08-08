import { useState, type CSSProperties, type MouseEvent } from 'react';

/**
 * A product photo inside a tinted tile — the grid card's square thumb and the
 * detail overlay's 4:3 figure are the same component at different ratios.
 *
 * Deliberately dumb: the <img> is rendered straight away with no per-mount
 * "loading" state and no opacity gate. The previous implementation faded in on
 * every mount, and because the grid is virtualised, scrolling back over a card
 * remounted it — so a fully cached image visibly blanked and repopulated. An
 * <img> the browser already has decoded now paints in the same frame.
 *
 * The tile owns the framing (tint, padding, centring) and the image is always
 * `contain`-fitted, so nothing is ever cropped and the off-centre crops of the
 * old `object-cover` build cannot recur. A near-white tint is deliberate:
 * Encore's shots are mostly white-background cut-outs, so they blend into the
 * tile instead of floating in a black box.
 *
 * With `href` the tile becomes a link to the Encore listing. That is a real
 * anchor rather than a middle-click handler so the browser's own affordances
 * come free: middle-click, ⌘/Ctrl-click, right-click → "Open in new tab", and
 * the URL in the status bar on hover. A plain left click still belongs to the
 * card, which opens the detail overlay.
 */

/**
 * URLs whose fetch already failed. Module-level and deliberately not React
 * state: a broken CDN URL stays broken, and re-requesting it every time its
 * card scrolls back into view would be pure waste on venue wifi.
 */
const failedUrls = new Set<string>();

interface Props {
  src: string | null;
  alt: string;
  /** Padding inside the tile — narrower columns get less. */
  pad: number;
  /** Tile tint token index, 0–7. */
  tint: number;
  /** CSS aspect-ratio for the tile. */
  ratio?: string;
  /** Drawn-fallback size as a fraction of the tile. */
  fallback?: { w: string; h: string; radius: number };
  /** Makes the tile a link to the lot's page on Encore. */
  href?: string;
}

const CARD_FALLBACK = { w: '56%', h: '56%', radius: 7 };

export function TileImage({ src, alt, pad, tint, ratio = '1 / 1', fallback, href }: Props) {
  const [, forceRender] = useState(0);
  const broken = src === null || failedUrls.has(src);
  const shape = fallback ?? CARD_FALLBACK;

  const tileStyle: CSSProperties = {
    position: 'relative',
    aspectRatio: ratio,
    background: `var(--t${tint})`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: pad,
    overflow: 'hidden',
  };

  /**
   * A modified click is the user asking for a new tab: let the browser have it,
   * and stop it bubbling so the detail overlay doesn't also open behind. A
   * plain click is cancelled here and handled by the card. Middle-click fires
   * `auxclick`, not `click`, so it never reaches this at all — which is the
   * whole point of using an anchor.
   */
  const onAnchorClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey) {
      e.stopPropagation();
      return;
    }
    e.preventDefault();
  };

  const content = broken ? (
    <FallbackShape {...shape} />
  ) : (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      draggable={false}
      onError={() => {
        failedUrls.add(src);
        forceRender((n) => n + 1);
      }}
      style={{
        maxWidth: '100%',
        maxHeight: '100%',
        objectFit: 'contain',
        display: 'block',
      }}
    />
  );

  if (!href) return <div style={tileStyle}>{content}</div>;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title="Open on Encore"
      data-testid="tile-link"
      // The card is already the tab stop, and the detail overlay carries the
      // real labelled link.
      tabIndex={-1}
      // A link is natively draggable and long-pressable; either one would eat a
      // swipe that starts on the image.
      draggable={false}
      onClick={onAnchorClick}
      style={{ ...tileStyle, WebkitTouchCallout: 'none' }}
    >
      {content}
    </a>
  );
}

/** Drawn placeholder for a lot with no photo, or one whose photo 404s. */
function FallbackShape({ w, h, radius }: { w: string; h: string; radius: number }) {
  return (
    <div
      aria-hidden
      style={{
        width: w,
        height: h,
        border: '1.5px solid var(--ink)',
        borderRadius: radius,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          width: '26%',
          aspectRatio: '1 / 1',
          borderRadius: '50%',
          background: 'var(--ink)',
        }}
      />
    </div>
  );
}
