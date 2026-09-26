'use client';

import { Microphone } from '@phosphor-icons/react';

interface ChatLauncherProps {
  onOpen: () => void;
}

export function ChatLauncher({ onOpen }: ChatLauncherProps) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-6 z-40 flex justify-center px-4 md:justify-end md:pr-10">
      <button
        type="button"
        onClick={onOpen}
        className="group pointer-events-auto relative flex max-w-xl items-center outline-none"
        aria-label="Open text chat with Game Guide"
      >
        <div className="relative flex min-w-[min(100%,20rem)] items-center gap-3 rounded-full border-2 border-violet-500/90 bg-black px-5 py-4 shadow-[0_0_40px_-8px_rgba(139,92,246,0.55)] transition group-hover:border-violet-400 group-hover:shadow-[0_0_48px_-6px_rgba(139,92,246,0.7)] md:min-w-[22rem] md:px-8 md:py-5">
          <Microphone className="size-5 shrink-0 text-violet-400" weight="fill" />
          <p className="text-left text-sm leading-snug text-zinc-100 md:text-base">
            Got a question? I&apos;m happy to help.
            <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-violet-400 align-middle" />
          </p>
        </div>
      </button>
    </div>
  );
}
