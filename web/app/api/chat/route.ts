import { loadMonorepoEnv, readEnvVar } from '@/lib/env';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function chatApiBaseUrl(): string {
  loadMonorepoEnv();
  return readEnvVar('CHAT_API_URL') || 'http://127.0.0.1:8765';
}

export async function POST(req: Request) {
  const body = await req.text();
  let upstream: Response;
  try {
    upstream = await fetch(`${chatApiBaseUrl()}/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
  } catch {
    return new Response(
      JSON.stringify({
        error: 'Chat API is not running. Start it with: cd catalog && uv run catalog-chat-api',
      }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return new Response(text || 'Chat API error', { status: upstream.status });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
    },
  });
}
