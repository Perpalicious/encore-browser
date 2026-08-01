import { useEffect, type CSSProperties } from 'react';
import type { LotView } from '../lib/lotView';
import { conditionColor } from '../lib/lotView';
import { formatMoney } from '../lib/resale';
import { TileImage } from './pills/TileImage';

/**
 * The lot detail overlay — docs/design/README.md § "Detail overlay".
 *
 * This is the fix for the inline-expand problem: expansion never happens inside
 * the grid, so the grid never reflows and keeps its scroll position. On a
 * pointing device it is a right drawer; on a touch device (by INPUT, not just
 * width — an iPad gets the desktop grid but sheet affordances) it is a bottom
 * sheet. Both sit above a scrim that closes on click, and Escape also closes.
 *
 * ‹ › step to the previous/next lot in the current result set WITHOUT closing,
 * so you can walk a filtered shortlist without going back to the grid.
 */

interface Props {
  view: LotView;
  /** Position in the current result set, for the ‹ › stepper. */
  index: number;
  total: number;
  sheet: boolean;
  watched: boolean;
  onClose: () => void;
  onStep: (delta: number) => void;
  onToggleWatch: () => void;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

const microLabel: CSSProperties = {
  fontFamily: MONO,
  fontWeight: 500,
  fontSize: '8.5px',
  letterSpacing: '.13em',
  color: 'var(--dim3)',
};

const figure: CSSProperties = {
  fontFamily: MONO,
  fontWeight: 500,
  fontSize: '17px',
  lineHeight: 1,
  fontVariantNumeric: 'tabular-nums',
};

const pill: CSSProperties = {
  fontFamily: MONO,
  fontWeight: 500,
  fontSize: '9px',
  letterSpacing: '.08em',
  padding: '4px 7px',
  borderRadius: 5,
  background: 'var(--s3)',
  whiteSpace: 'nowrap',
};

const stepButton: CSSProperties = {
  width: 34,
  height: 36,
  borderRadius: 9,
  border: '1px solid var(--line)',
  color: 'var(--dim2)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
};

/** Green / blue / grey for High / Medium / Low. */
function confidenceColor(conf: string | null): string {
  if (conf === 'high') return 'var(--c-new)';
  if (conf === 'medium') return 'var(--c-like)';
  return 'var(--dim2)';
}

/**
 * Green / amber / red. The handoff assumes a fourth 'Strong' value above
 * 'Good'; our resale pass only ever emits poor/fair/good, so 'good' takes the
 * top colour and nothing here invents a fourth step.
 */
function outlookColor(out: string | null): string {
  if (out === 'good') return 'var(--c-new)';
  if (out === 'fair') return 'var(--c-fair)';
  return 'var(--c-heavy)';
}

/** "$40–$70", or a single bound when only one is priced. */
function rangeLabel(view: LotView): string {
  const { lo, hi } = view;
  if (lo !== null && hi !== null) return `${formatMoney(lo)}–${formatMoney(hi)}`;
  if (lo !== null) return `≥ ${formatMoney(lo)}`;
  if (hi !== null) return `≤ ${formatMoney(hi)}`;
  return '—';
}

export function LotDetail({
  view,
  index,
  total,
  sheet,
  watched,
  onClose,
  onStep,
  onToggleWatch,
}: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const cc = conditionColor(view.cond);
  const panelPosition: CSSProperties = sheet
    ? {
        left: 0,
        right: 0,
        bottom: 0,
        height: '88dvh',
        borderRadius: '18px 18px 0 0',
        animation: 'sheetup .18s ease-out',
      }
    : {
        top: 0,
        right: 0,
        bottom: 0,
        width: 430,
        borderLeft: '1px solid var(--line)',
        animation: 'slidein .16s ease-out',
      };

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'var(--ov)',
          zIndex: 60,
          animation: 'fadein .14s ease-out',
        }}
      />
      <div
        data-testid="lot-detail"
        data-lot-number={view.lot}
        role="dialog"
        aria-modal="true"
        aria-label={view.title}
        style={{
          position: 'fixed',
          zIndex: 61,
          background: 'var(--surface)',
          boxShadow: 'var(--sh)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          ...panelPosition,
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflowY: 'auto' }}>
          <div style={{ padding: '14px 16px 0', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <div
              className="lot-card__title"
              style={{ flex: 1, fontWeight: 600, fontSize: '16px', lineHeight: 1.3 }}
            >
              {view.title}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close details"
              style={{
                width: 28,
                height: 28,
                flex: 'none',
                borderRadius: 8,
                background: 'var(--s2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '14px',
                color: 'var(--dim2)',
              }}
            >
              ✕
            </button>
          </div>

          <div style={{ padding: '12px 16px 0' }}>
            <div style={{ borderRadius: 11, overflow: 'hidden' }}>
              <TileImage
                src={view.imgFull}
                alt={view.title}
                pad={16}
                tint={view.tint}
                ratio="4 / 3"
                fallback={{ w: '44%', h: '52%', radius: 9 }}
              />
            </div>
          </div>

          <div
            style={{
              padding: '12px 16px 0',
              display: 'flex',
              alignItems: 'center',
              gap: 9,
              flexWrap: 'wrap',
            }}
          >
            {view.cond && (
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  fontFamily: MONO,
                  fontWeight: 500,
                  fontSize: '9.5px',
                  letterSpacing: '.08em',
                  color: cc,
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: cc }} />
                {view.cond.toUpperCase()}
              </span>
            )}
            <span style={{ fontFamily: MONO, fontSize: '9.5px', color: 'var(--dim3)' }}>
              {view.day === 'M' ? 'MONDAY' : 'SUNDAY'} · LOT {view.lot}
            </span>
            {view.tick && (
              <span
                data-testid="top-decile-badge"
                style={{
                  fontFamily: MONO,
                  fontWeight: 700,
                  fontSize: '8.5px',
                  letterSpacing: '.08em',
                  padding: '3px 6px',
                  borderRadius: 4,
                  background: 'var(--pick)',
                  color: '#fff',
                }}
              >
                ▲ TOP-DECILE SPREAD
              </span>
            )}
          </div>

          {(view.mid !== null || view.retail !== null) && (
            <div style={{ padding: '12px 16px 0' }}>
              <div
                data-testid="resale-detail"
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 16,
                  padding: '11px 13px',
                  borderRadius: 10,
                  background: 'var(--s2)',
                }}
              >
                {view.mid !== null && (
                  <div>
                    <div style={{ ...microLabel, marginBottom: 5 }}>RESALE</div>
                    <div style={{ ...figure, color: 'var(--text)' }}>{rangeLabel(view)}</div>
                  </div>
                )}
                {view.retail !== null && (
                  <div>
                    <div style={{ ...microLabel, marginBottom: 5 }}>RETAIL</div>
                    <div style={{ ...figure, fontWeight: 400, color: 'var(--dim3)' }}>
                      {formatMoney(view.retail)}
                    </div>
                  </div>
                )}
                <div
                  style={{
                    marginLeft: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 5,
                    alignItems: 'flex-end',
                  }}
                >
                  {view.conf && (
                    <span
                      data-testid="resale-confidence"
                      style={{ ...pill, color: confidenceColor(view.conf) }}
                    >
                      {view.conf.toUpperCase()} CONFIDENCE
                    </span>
                  )}
                  {view.out && (
                    <span
                      data-testid="resale-outlook"
                      style={{ ...pill, color: outlookColor(view.out) }}
                    >
                      {view.out.toUpperCase()} OUTLOOK
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          <div
            style={{ padding: '12px 16px 0', display: 'flex', flexDirection: 'column', gap: 7 }}
          >
            <MetaRow label="CATEGORY" value={view.cat} strong />
            <MetaRow label="SUB" value={view.sub || '—'} />
            <MetaRow label="BUCKET" value={view.buckets.length > 0 ? view.buckets.join(', ') : '—'} />
          </div>

          {view.note && (
            <div style={{ padding: '12px 16px 0' }}>
              <div style={{ fontSize: '12px', lineHeight: 1.6, color: 'var(--dim)' }}>
                {view.note}
              </div>
            </div>
          )}

          {view.pick && (
            <div style={{ padding: '12px 16px 0' }}>
              <div
                data-testid="personal-detail"
                style={{
                  padding: '11px 13px',
                  borderRadius: 10,
                  background: 'rgba(139,107,255,.1)',
                  border: '1px solid rgba(139,107,255,.22)',
                }}
              >
                <div
                  style={{
                    fontFamily: MONO,
                    fontWeight: 500,
                    fontSize: '9px',
                    letterSpacing: '.11em',
                    color: 'var(--lavt)',
                    marginBottom: 6,
                  }}
                >
                  PERSONAL PICK{view.strength ? ` · ${view.strength.toUpperCase()} MATCH` : ''}
                </div>
                {view.match && (
                  <div
                    data-testid="personal-reasoning"
                    style={{ fontSize: '11.5px', lineHeight: 1.55, color: 'var(--dim)' }}
                  >
                    {view.match}
                  </div>
                )}
                {view.src.personal_tags && view.src.personal_tags.length > 0 && (
                  <div
                    data-testid="personal-tags"
                    style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 5 }}
                  >
                    {view.src.personal_tags.map((t) => (
                      <span key={t} style={{ ...pill, color: 'var(--dim2)', letterSpacing: '.04em' }}>
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          <div
            style={{
              padding: '14px 16px 18px',
              marginTop: 'auto',
              display: 'flex',
              alignItems: 'center',
              gap: 9,
            }}
          >
            <a
              href={view.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                flex: 1,
                padding: '11px 0',
                textAlign: 'center',
                borderRadius: 9,
                background: 'var(--lav)',
                color: 'var(--onlav)',
                fontSize: '12.5px',
                fontWeight: 600,
              }}
            >
              View on Encore ↗
            </a>
            <button
              type="button"
              data-testid="detail-star-btn"
              onClick={onToggleWatch}
              aria-pressed={watched}
              aria-label={`${watched ? 'Remove from list' : 'Add to list'}: ${view.title}`}
              style={{
                padding: '11px 13px',
                borderRadius: 9,
                border: '1px solid var(--line)',
                fontSize: '12px',
                fontWeight: 500,
                color: watched ? 'var(--star2)' : 'var(--dim2)',
              }}
            >
              {watched ? '★' : '☆'}
            </button>
            <button
              type="button"
              data-testid="detail-prev"
              onClick={() => onStep(-1)}
              disabled={index <= 0}
              aria-label="Previous lot"
              style={{ ...stepButton, opacity: index <= 0 ? 0.4 : 1 }}
            >
              ‹
            </button>
            <button
              type="button"
              data-testid="detail-next"
              onClick={() => onStep(1)}
              disabled={index >= total - 1}
              aria-label="Next lot"
              style={{ ...stepButton, opacity: index >= total - 1 ? 0.4 : 1 }}
            >
              ›
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

function MetaRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <span style={{ ...microLabel, width: 66, flex: 'none', paddingTop: 2 }}>{label}</span>
      <span
        style={{
          fontSize: '12px',
          fontWeight: strong ? 500 : 400,
          color: strong ? 'var(--text)' : 'var(--dim)',
        }}
      >
        {value}
      </span>
    </div>
  );
}
