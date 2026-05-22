interface Props {
  label: string;
  children: React.ReactNode;
}

export function FilterFieldRow({ label, children }: Props) {
  return (
    <div className="flex items-center gap-3">
      <span className="shrink-0 w-[68px] text-[11px] font-mono uppercase tracking-[0.14em] text-ink2 dark:text-bone2">
        {label}
      </span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}
