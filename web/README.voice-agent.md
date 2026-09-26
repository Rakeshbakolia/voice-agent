# Game Guide web app (`web/`)

Next.js + React frontend for the **voice-agent** monorepo. See the [root README](../README.md) for full setup.

Based on [LiveKit agent-starter-react](https://github.com/livekit-examples/agent-starter-react), customized with a dark **Game Guide** shell: **home + streaming text chat**, and **`/voice`** for LiveKit.

## Prerequisites

- Node 20+ and [pnpm](https://pnpm.io/)
- LiveKit credentials (same project as `agent/`)
- Python agent running: `cd agent && lk agent dev`

## Setup

```bash
cd web
pnpm install
cp .env.example .env.local
```

Copy from the repo root `.env.local` into `web/.env.local`:

```env
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
AGENT_NAME=agent
```

## Run

Text chat needs `catalog-chat-api` (see root README). Voice needs `lk agent dev`.

```bash
# From repo root — use separate terminals
docker compose up -d
cd catalog && uv run catalog-chat-api
cd web && npm run dev          # or pnpm dev
cd agent && lk agent dev       # optional, for /voice
```

Open http://localhost:3000 for text chat; http://localhost:3000/voice for voice.

## Docs

See [docs/frontend/README.md](../docs/frontend/README.md) for architecture and roadmap.
