'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { PaperPlaneRight, X } from '@phosphor-icons/react';
import { type ChatMessage, newMessageId, streamChat } from '@/lib/parse-chat-stream';
import { cn } from '@/lib/shadcn/utils';

interface TextChatPanelProps {
  open: boolean;
  onClose: () => void;
}

export function TextChatPanel({ open, onClose }: TextChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Hi! I’m Game Guide. Ask me for recommendations—try “best RPGs on PS5” or “cozy co-op on Switch.”',
    },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, status]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) {
      return;
    }

    const userMsg: ChatMessage = { id: newMessageId(), role: 'user', content: text };
    const assistantId = newMessageId();
    const history = [...messages.filter((m) => m.id !== 'welcome'), userMsg];

    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: 'assistant', content: '' }]);
    setInput('');
    setIsStreaming(true);
    setStatus(null);

    await streamChat(
      history.map((m) => ({ role: m.role, content: m.content })),
      {
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m))
          );
        },
        onToolStart: (name) => setStatus(`Searching catalog (${name})…`),
        onToolEnd: () => setStatus(null),
        onError: (message) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Sorry, something went wrong: ${message}` }
                : m
            )
          );
        },
        onDone: () => setIsStreaming(false),
      }
    );
    setIsStreaming(false);
    setStatus(null);
  }, [input, isStreaming, messages]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 backdrop-blur-sm md:items-center"
      role="dialog"
      aria-label="Game Guide text chat"
    >
      <div className="flex h-[min(85vh,640px)] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-zinc-800 bg-[#0c0c0c] shadow-2xl">
        <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Game Guide</h2>
            <p className="text-xs text-zinc-500">Text chat · streaming</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-zinc-400 hover:bg-zinc-800 hover:text-white"
            aria-label="Close chat"
          >
            <X className="size-5" />
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {messages.map((m) => (
            <div
              key={m.id}
              className={cn(
                'max-w-[90%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
                m.role === 'user'
                  ? 'ml-auto bg-violet-600 text-white'
                  : 'mr-auto border border-zinc-800 bg-zinc-900 text-zinc-200'
              )}
            >
              {m.content || (m.role === 'assistant' && isStreaming ? '…' : '')}
            </div>
          ))}
          {status && <p className="text-center text-xs text-violet-400">{status}</p>}
        </div>

        <form
          className="border-t border-zinc-800 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <div className="flex items-center gap-2 rounded-full border border-violet-500/50 bg-black px-3 py-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isStreaming}
              placeholder="Ask about games…"
              className="min-w-0 flex-1 bg-transparent text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
            />
            <button
              type="submit"
              disabled={isStreaming || !input.trim()}
              className="rounded-full bg-violet-600 p-2 text-white disabled:opacity-40"
              aria-label="Send message"
            >
              <PaperPlaneRight className="size-4" weight="fill" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
