export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
}

export type StreamHandlers = {
  onToken: (text: string) => void;
  onToolStart?: (name: string) => void;
  onToolEnd?: (name: string) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
};

export async function streamChat(
  messages: Pick<ChatMessage, 'role' | 'content'>[],
  handlers: StreamHandlers
): Promise<void> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  });

  if (!response.ok) {
    const text = await response.text();
    handlers.onError?.(text || `Chat failed (${response.status})`);
    handlers.onDone?.();
    return;
  }

  if (!response.body) {
    handlers.onError?.('No response body');
    handlers.onDone?.();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      const lines = part.split('\n');
      let eventType = 'message';
      let dataLine = '';
      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLine = line.slice(5).trim();
        }
      }
      if (!dataLine) {
        continue;
      }
      try {
        const data = JSON.parse(dataLine) as Record<string, unknown>;
        if (eventType === 'token' && typeof data.text === 'string') {
          handlers.onToken(data.text);
        } else if (eventType === 'tool_start' && typeof data.name === 'string') {
          handlers.onToolStart?.(data.name);
        } else if (eventType === 'tool_end' && typeof data.name === 'string') {
          handlers.onToolEnd?.(data.name);
        } else if (eventType === 'error' && typeof data.message === 'string') {
          handlers.onError?.(data.message);
        } else if (eventType === 'done') {
          handlers.onDone?.();
        }
      } catch {
        // ignore malformed chunks
      }
    }
  }
  handlers.onDone?.();
}

export function newMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}
