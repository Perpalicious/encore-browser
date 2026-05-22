import { useState, useEffect } from 'react';
import { ImageOff } from 'lucide-react';

interface Props {
  src: string;
  alt: string;
  aspect?: string;
  className?: string;
}

export function LotImage({ src, alt, aspect = 'aspect-[4/3]', className = '' }: Props) {
  const [state, setState] = useState<'loading' | 'loaded' | 'broken'>(
    src ? 'loading' : 'broken'
  );

  useEffect(() => {
    setState(src ? 'loading' : 'broken');
  }, [src]);

  return (
    <div
      className={`relative ${aspect} w-full overflow-hidden bg-paper2 dark:bg-coal ${className}`}
    >
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
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${
              state === 'loaded' ? 'opacity-100' : 'opacity-0'
            }`}
            draggable={false}
          />
        </>
      )}
    </div>
  );
}
