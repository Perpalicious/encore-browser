import { useState } from 'react';

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
}

const CARD_FALLBACK = { w: '56%', h: '56%', radius: 7 };

export function TileImage({ src, alt, pad, tint, ratio = '1 / 1', fallback }: Props) {
  const [, forceRender] = useState(0);
  const broken = src === null || failedUrls.has(src);
  const shape = fallback ?? CARD_FALLBACK;

  return (
    <div
      style={{
        position: 'relative',
        aspectRatio: ratio,
        background: `var(--t${tint})`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: pad,
        overflow: 'hidden',
      }}
    >
      {broken ? (
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
      )}
    </div>
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
