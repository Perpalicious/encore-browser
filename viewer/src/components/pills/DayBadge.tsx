interface Props {
  day: string;
  className?: string;
}

export function DayBadge({ day, className = '' }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] font-medium ${className}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          day === 'Sunday' ? 'bg-ember' : 'bg-indigo-500 dark:bg-indigo-400'
        }`}
      />
      {day}
    </span>
  );
}
