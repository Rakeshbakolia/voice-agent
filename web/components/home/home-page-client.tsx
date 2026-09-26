'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  GameController,
  MagnifyingGlass,
  MicrophoneStage,
  Ranking,
  Sparkle,
} from '@phosphor-icons/react';
import { ChatLauncher } from '@/components/home/chat-launcher';
import { TextChatPanel } from '@/components/home/text-chat-panel';
import { Button } from '@/components/ui/button';

const features = [
  {
    icon: MicrophoneStage,
    title: 'Talk naturally',
    body: 'Voice on /voice, or text chat from the bar below.',
  },
  {
    icon: Ranking,
    title: 'Ratings you can trust',
    body: 'Recommendations come from your catalog in Postgres.',
  },
  {
    icon: MagnifyingGlass,
    title: 'Search by vibe',
    body: 'Semantic search over 190k+ game descriptions.',
  },
  {
    icon: Sparkle,
    title: 'One assistant',
    body: 'Same tools for text and voice—platform, genre, and mood.',
  },
];

const steps = [
  'Pick your platform (PlayStation, Xbox, Nintendo, PC).',
  'Say what you are in the mood for—genre, co-op, story-heavy, or a title you love.',
  'Get a short list of picks; ask for details or more anytime.',
];

export function HomePageClient() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="relative pb-36">
      <section className="mx-auto max-w-3xl px-6 pt-20 pb-16 text-center md:pt-28">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-xs font-medium text-violet-200">
          <GameController className="size-4" weight="fill" />
          Voice &amp; text game discovery
        </div>
        <h1 className="text-4xl font-semibold tracking-tight text-white md:text-5xl">
          Meet <span className="text-violet-400">Game Guide</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-zinc-400 md:text-lg">
          Your personal assistant for video game recommendations—a rich multi-platform catalog with
          live text chat and optional voice on /voice.
        </p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Button
            type="button"
            size="lg"
            className="rounded-full bg-violet-600 px-8 hover:bg-violet-500"
            onClick={() => setChatOpen(true)}
          >
            Open text chat
          </Button>
          <Button
            asChild
            variant="outline"
            size="lg"
            className="rounded-full border-zinc-700 bg-transparent text-zinc-200 hover:bg-zinc-900"
          >
            <Link href="/voice">Voice chat</Link>
          </Button>
        </div>
      </section>

      <section className="border-y border-zinc-800/80 bg-zinc-950/50">
        <div className="mx-auto grid max-w-5xl gap-8 px-6 py-16 sm:grid-cols-2">
          {features.map(({ icon: Icon, title, body }) => (
            <article
              key={title}
              className="rounded-2xl border border-zinc-800/80 bg-[#0a0a0a] p-6 text-left"
            >
              <Icon className="mb-3 size-8 text-emerald-400" weight="duotone" />
              <h2 className="text-lg font-medium text-zinc-100">{title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-zinc-500">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-2xl px-6 py-16">
        <h2 className="text-center text-2xl font-semibold text-white">How it works</h2>
        <ol className="mt-10 space-y-6">
          {steps.map((step, index) => (
            <li key={step} className="flex gap-4 text-left">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-violet-600/20 text-sm font-semibold text-violet-300">
                {index + 1}
              </span>
              <p className="pt-1 text-sm leading-relaxed text-zinc-400 md:text-base">{step}</p>
            </li>
          ))}
        </ol>
      </section>

      <ChatLauncher onOpen={() => setChatOpen(true)} />
      <TextChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
