'use client';

import { cn } from '@/lib/shadcn/utils';

const PLATFORMS = ['PS5', 'Switch', 'PC', 'Xbox'] as const;
const GENRES = ['RPG', 'Action', 'Adventure', 'Co-op'] as const;

interface PlatformChipsProps {
  className?: string;
}

/** Quick prompts — user can say these aloud or tap to copy intent (visual only for now). */
export function PlatformChips({ className }: PlatformChipsProps) {
  return (
    <div className={cn('flex max-w-md flex-col gap-3', className)}>
      <ChipRow label="Platform" items={PLATFORMS} />
      <ChipRow label="Genre" items={GENRES} />
    </div>
  );
}

function ChipRow({ label, items }: { label: string; items: readonly string[] }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <span className="w-full text-[10px] font-medium tracking-wider text-zinc-500 uppercase">
        {label}
      </span>
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border border-zinc-700/80 bg-zinc-900/80 px-3 py-1 text-xs text-zinc-300"
        >
          {item}
        </span>
      ))}
    </div>
  );
}
