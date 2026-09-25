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
| **Wikipedia / Wikidata** | Sparse ratings; weak for “best RPG on PS5” | Identifier enrichment only |
| **Metacritic unofficial JSON** | No official API; ToS / scraping risk | After IGDB/RAWG baseline |
| **PlayStation Store scrapers** | Scraping + legal review | Optional Sony-only enrich |

---

## Phase 2 — API key / OAuth required

| Source | Auth | CLI | Status |
|--------|------|-----|--------|
| **IGDB (Twitch)** | `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` | `catalog-ingest igdb` | **Done** |
| **RAWG** | `RAWG_API_KEY` | `catalog-ingest rawg` | **Done** |
| **Steam Web API** | `STEAM_WEB_API_KEY` | `catalog-ingest steam-api` | **Done** |
| **GameBrain** | `GAMEBRAIN_API_KEY` | `catalog-ingest gamebrain` | **Done** |
| **Steam Dataset 2025** (Zenodo CSV/Parquet) | Download only | `catalog-ingest steam-dataset` | **Partial** (~150k PC rows from `applications.csv`; full ~239k optional) |
| **MobyGames** | Paid subscription | — | **Skipped** |

```bash
# .env.local: TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
cd catalog && uv run catalog-ingest igdb --games-per-platform 50

# PS5 only, small test
uv run catalog-ingest igdb --platform-ids 167 --games-per-platform 25

# Steam Web API + GameBrain (Phase 2 remainder)
uv run catalog-ingest steam-api --list-limit 300 --enrich-limit 40 --delay 1.25
uv run catalog-ingest gamebrain --limit-per-platform 40
uv run catalog-ingest phase2   # both with defaults

# Steam Dataset 2025 (Zenodo: applications.csv + application_genres.csv + genres.csv)
uv run catalog-ingest steam-dataset \
  --file ~/Downloads/steam_dataset_2025_csv/applications.csv \
  --genres-file ~/Downloads/steam_dataset_2025_csv/application_genres.csv \
  --genre-names-file ~/Downloads/steam_dataset_2025_csv/genres.csv
# Full multi-source replay: catalog/scripts/full_ingest.sh (steam-dataset is the long step)

# RAWG
uv run catalog-ingest rawg --games-per-platform 50
uv run catalog-ingest rawg --platform-ids 187,7,4 --games-per-platform 25
```

**Env vars:** `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `STEAM_WEB_API_KEY`, `GAMEBRAIN_API_KEY`, optional `RAWG_API_KEY`

---

## Phase 3 — Agent / embeddings

- [x] Embedding job — `catalog-embed run` (`catalog/embeddings.py`, OpenAI `text-embedding-3-small`, dim **1536**)
- [x] LiveKit **function tools** — `search_games`, `search_similar_games`, `get_game_details`, `list_catalog_filters` (`agent/src/game_tools.py`)
- [ ] Automated merge of duplicate titles (`catalog-embed stats --dedup` reports only; merge via `game_external_id` TBD)

```bash
cd catalog && uv run catalog-embed stats
uv run catalog-embed run --limit 5000 --batch-size 64   # pilot before full ~194k chunks
```

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
