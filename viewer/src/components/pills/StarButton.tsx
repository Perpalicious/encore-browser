import { Star } from 'lucide-react';

interface Props {
  watched: boolean;
  onToggle: () => void;
}

export function StarButton({ watched, onToggle }: Props) {
  return (
    <button
      type="button"
      data-testid="star-btn"
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      aria-label={watched ? 'Remove from watched' : 'Add to watched'}
      aria-pressed={watched}
      className={`absolute top-2.5 right-2.5 z-10 h-11 w-11 grid place-items-center rounded-full
                  backdrop-blur-md transition-all
                  ${
                    watched
                      ? 'bg-ember text-white shadow-pop hover:bg-ember2'
                      : 'bg-white/85 text-ink/80 hover:bg-white hover:text-ember shadow ring-1 ring-black/5 dark:bg-night2/85 dark:text-bone/80 dark:ring-white/10 dark:hover:text-ember'
                  }`}
    >
      <Star size={20} strokeWidth={2} fill={watched ? 'currentColor' : 'none'} />
    </button>
  );
}
