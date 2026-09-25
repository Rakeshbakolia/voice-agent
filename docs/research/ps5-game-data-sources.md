# Game data sources — ingestion status

> **Research reference:** Full API notes live in [`game-data-sources.md`](./game-data-sources.md).  
> This file tracks **what we implemented** vs **what is still pending** for the voice-agent catalog + RAG (`game`, `game_platform`, `game_chunk`).

**Last updated:** 2026-09-25

---

## Phase 1 — No API key / no signup (implemented)

| Source | Role | CLI | Stored as | Status |
|--------|------|-----|-----------|--------|
| **[OpenVGDB](https://github.com/OpenVGDB/OpenVGDB/releases)** | Legacy + console catalog (PS1, PSP, NDS, SNES, NGC, …) | `catalog-ingest openvgdb` | `game` + `game_platform` + `game_genre` + `game_chunk` (text); `game_external_id.source = openvgdb` | **Done** |
| **[Steam Store `appdetails`](https://store.steampowered.com/api/appdetails)** | Modern PC titles, Metacritic, descriptions | `catalog-ingest steam-store` | Same tables; `source = steam`; platform `pc-windows` | **Done** |
| **Both** | Dev bootstrap | `catalog-ingest no-auth` | Runs OpenVGDB (default 3000 rows) + Steam (default 25 apps) | **Done** |

**RAG note:** Ingest writes **plain-text** rows in `game_chunk` (`embedding` is `NULL` until a separate embedding job runs).

**Code:** `catalog/src/catalog/ingest/` · **Seed Steam IDs:** `catalog/src/catalog/data/steam_seed_appids.txt`

### Commands

```bash
docker compose up -d
cd catalog && uv sync

# OpenVGDB only (downloads ~40MB sqlite on first run into repo .cache/openvgdb/)
uv run catalog-ingest openvgdb --limit 2000 --systems PSX,PSP,NGC

# Steam store metadata (rate-limited; no API key)
uv run catalog-ingest steam-store --limit 20 --delay 1.25

# Both
uv run catalog-ingest no-auth --openvgdb-limit 1500 --steam-limit 15
```

---

## Phase 1 — No auth considered but not implemented yet

| Source | Why skipped for now | Planned |
|--------|---------------------|---------|
| **[OpenVGDB only — full 53k rows / MAME]** | MAME arcade (`MAME` system) is huge and poor fit for recommender voice flow | Optional `--systems` without default cap |
| **[Steam Dataset 2025](https://github.com/vintagedon/steam-dataset-2025)** | Large static dump; overlaps `appdetails` for MVP | Offline CSV import job |
| **Wikipedia / Wikidata** | Sparse ratings; weak for “best RPG on PS5” | Identifier enrichment only |
| **Metacritic unofficial JSON** | No official API; ToS / scraping risk | After IGDB/RAWG baseline |
| **PlayStation Store scrapers** | Scraping + legal review | Optional Sony-only enrich |

---

## Phase 2 — API key / OAuth required

| Source | Auth | CLI | Status |
|--------|------|-----|--------|
| **IGDB (Twitch)** | `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` | `catalog-ingest igdb` | **Done** |
| **RAWG** | `RAWG_API_KEY` | (pending) | Pending |
| **Steam Web API** | `STEAM_WEB_API_KEY` | (pending) | Pending |
| **GameBrain** | API key (+ attribution) | (pending) | Optional |
| **MobyGames** | Subscription / research waiver | (pending) | Optional |

```bash
# .env.local: TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
cd catalog && uv run catalog-ingest igdb --games-per-platform 50

# PS5 only, small test
uv run catalog-ingest igdb --platform-ids 167 --games-per-platform 25
```

**Env vars:** `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `RAWG_API_KEY`, `STEAM_WEB_API_KEY`, `GAMEBRAIN_API_KEY`

---

## Phase 3 — Agent / embeddings (pending)

- [ ] Embedding job for `game_chunk.embedding` (e.g. OpenAI / local model, dim **1536**)
- [ ] LiveKit **function tools** reading Postgres (genre + platform + rating dimension)
- [ ] Merge duplicate titles across `openvgdb` / `steam` / IGDB via `game_external_id`

---

## Quick counts after ingest

```bash
cd catalog && uv run python -c "
from sqlalchemy import func, select
from catalog import Game, GameChunk, IngestionRun
from catalog.database import get_session_factory
with get_session_factory()() as s:
    print('games', s.scalar(select(func.count()).select_from(Game)))
    print('chunks', s.scalar(select(func.count()).select_from(GameChunk)))
    runs = s.scalars(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(3))
    for r in runs:
        print(r.source, r.status, r.stats)
"
```
