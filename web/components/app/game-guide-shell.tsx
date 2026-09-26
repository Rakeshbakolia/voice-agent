'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChatCircle, GameController, House } from '@phosphor-icons/react';
import { cn } from '@/lib/shadcn/utils';

interface GameGuideShellProps {
  children: React.ReactNode;
}

export function GameGuideShell({ children }: GameGuideShellProps) {
  const pathname = usePathname();
  const isHome = pathname === '/';
  const isVoice = pathname.startsWith('/voice');

  return (
    <div className="flex h-svh w-full bg-[#0a0a0a] text-zinc-100">
      <aside
        className="hidden w-56 shrink-0 flex-col border-r border-zinc-800/80 bg-[#050505] md:flex"
        aria-label="Navigation"
      >
        <div className="flex items-center gap-2 px-4 py-5">
          <GameController className="size-6 text-emerald-400" weight="fill" />
          <Link href="/" className="text-sm font-semibold tracking-tight hover:text-white">
            Game Guide
          </Link>
        </div>
        <nav className="flex flex-col gap-1 px-2">
          <NavLink href="/" active={isHome} icon={House} label="Home" />
          <NavLink href="/voice" active={isVoice} icon={ChatCircle} label="Voice chat" />
          <NavItem disabled label="Saved lists" />
          <NavItem disabled label="Browse catalog" />
        </nav>
        <p className="mt-auto px-4 py-4 text-xs leading-relaxed text-zinc-500">
          Ask for games by platform, genre, or vibe. Powered by your local catalog.
        </p>
      </aside>
      <div className="relative min-w-0 flex-1 overflow-x-hidden overflow-y-auto">{children}</div>
    </div>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string;
  label: string;
  icon: typeof House;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
        active && 'bg-zinc-800/80 text-white',
        !active && 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
      )}
    >
      <Icon className="size-4 shrink-0" weight={active ? 'fill' : 'regular'} />
      {label}
    </Link>
  );
}

function NavItem({ label, disabled }: { label: string; disabled?: boolean }) {
  return (
    <span
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm',
        disabled && 'cursor-not-allowed text-zinc-600'
      )}
    >
      {label}
      {disabled && (
        <span className="ml-auto text-[10px] tracking-wide text-zinc-600 uppercase">Soon</span>
      )}
    </span>
  );
}
