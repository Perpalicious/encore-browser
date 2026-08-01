import type { GroupNode } from '../lib/batNav';

/**
 * Bat's List bucket picker — docs/design/README.md § "Bat's List empty state".
 *
 * Replaces the native <select> with the two-level group → bucket structure laid
 * out as cards and pills. Same information architecture, but the counts are
 * visible before you commit to a choice, which is the whole reason the level
 * exists.
 */

interface Props {
  groups: GroupNode[];
  group: string | null;
  bucket: string | null;
  onGroupChange: (g: string | null) => void;
  onBucketChange: (b: string | null) => void;
}

const MONO = "'JetBrains Mono', ui-monospace, monospace";

export function BatEmptyState({ groups, group, bucket, onGroupChange, onBucketChange }: Props) {
  const active = groups.find((g) => g.name === group) ?? null;

  return (
    <div
      data-testid="bat-prompt"
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 14,
        padding: '48px 16px 60px',
      }}
    >
      <div
        aria-hidden
        style={{
          width: 46,
          height: 46,
          borderRadius: 12,
          background: 'var(--lavbg)',
          border: '1px solid var(--lavbd)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '20px',
          color: 'var(--lavt)',
        }}
      >
        ✦
      </div>
      <div style={{ fontWeight: 600, fontSize: '15px', lineHeight: 1.3 }}>Pick a bucket</div>
      <div
        style={{
          fontSize: '12.5px',
          lineHeight: 1.5,
          color: 'var(--dim2)',
          textAlign: 'center',
          maxWidth: 320,
        }}
      >
        Bat's List is grouped. Choose a group, then a bucket inside it.
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: 8,
          maxWidth: 720,
          marginTop: 4,
        }}
      >
        {groups.map((g) => {
          const on = g.name === group;
          return (
            <button
              key={g.name}
              type="button"
              data-testid={`bat-group-${g.name}`}
              onClick={() => {
                // Always select — clicking the open group must not collapse it,
                // or the buckets you were reaching for vanish under the cursor.
                onGroupChange(g.name);
                onBucketChange(null);
              }}
              aria-pressed={on}
              style={{
                minWidth: 150,
                padding: '11px 13px',
                borderRadius: 11,
                textAlign: 'left',
                background: on ? 'var(--lavbg)' : 'var(--surface)',
                border: `1px solid ${on ? 'var(--lavbd)' : 'var(--line)'}`,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <span
                style={{ fontSize: '12.5px', fontWeight: 600, color: on ? 'var(--lavt)' : 'var(--text)' }}
              >
                {g.name}
              </span>
              <span
                style={{
                  fontFamily: MONO,
                  fontWeight: 500,
                  fontSize: '9px',
                  letterSpacing: '.11em',
                  color: 'var(--dim3)',
                }}
              >
                {g.count.toLocaleString('en-US')} LOTS
              </span>
            </button>
          );
        })}
      </div>

      {active && (
        <>
          <div style={{ width: '100%', maxWidth: 720, height: 1, background: 'var(--line2)' }} />
          <div
            data-testid="bat-buckets"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              gap: 7,
              maxWidth: 720,
            }}
          >
            {active.buckets.map((b) => {
              const on = b.name === bucket;
              return (
                <button
                  key={b.name}
                  type="button"
                  data-testid={`bat-bucket-${b.name}`}
                  onClick={() => onBucketChange(b.name)}
                  aria-pressed={on}
                  style={{
                    minHeight: 36,
                    padding: '8px 13px',
                    borderRadius: 20,
                    background: on ? 'var(--lavbg)' : 'var(--s2)',
                    border: `1px solid ${on ? 'var(--lavbd)' : 'var(--line)'}`,
                    fontSize: '12px',
                    fontWeight: 500,
                    color: on ? 'var(--lavt)' : 'var(--dim)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 7,
                  }}
                >
                  {b.name}
                  <span
                    style={{
                      fontFamily: MONO,
                      fontSize: '9.5px',
                      color: 'var(--dim3)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {b.count}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
