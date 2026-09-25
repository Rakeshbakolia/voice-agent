# Video game data — research sources (multi-platform)

Resources for building a **cross-platform** game recommender: PlayStation (PS1–PS5, Vita, …), Xbox (original → Series X|S), PC / **Steam**, Nintendo, mobile, and others. Includes **platform version** granularity where providers support it.

Last reviewed: 2026-09-25.

> **Ingestion tracker (implemented vs pending):** [`ps5-game-data-sources.md`](./ps5-game-data-sources.md)

---

## Can we do PlayStation / Xbox / Steam / others with versions?

**Yes.** You can model:

| Layer | Example | Typical source |
|--------|---------|----------------|
| **Parent brand** | PlayStation, Xbox, PC | RAWG `parent platforms`; IGDB `platform_family` |
| **Specific hardware / generation** | PS2, PS3, PS5, Xbox 360, Switch | IGDB `/platforms` (per-console IDs); RAWG `/platforms` |
| **Store / launcher** (PC) | Steam, Epic, GOG | IGDB `/external_games` + store enums; Steam Web API + Store API |
| **Release on a platform** | Same game, different dates/scores per platform | IGDB `/release_dates`; MobyGames `/games/{id}/platforms/{platform_id}` |

**Voice flow stays the same:** user picks **category (genre)** → **what matters (story / graphics / action / overall)** → recommend top titles **for the platform they asked about** (e.g. “on PS3” or “on Steam”).

Ingest once into **your database** with normalized tables: `platform`, `game`, `game_platform`, `genre`, `scores`.

---

## Product context

- Prefer **batch sync** (nightly jobs), not live third-party calls on every utterance.
- **Multi-axis ratings** (separate storyline / graphics / action numbers) are rarely provided by free APIs; use [rating dimensions](#rating-dimensions-storyline-graphics-action) below.

---

## Recommended primary sources (free or free tier)

### 1. IGDB (Twitch) — best single API for consoles + PC + store links

| | |
|---|---|
| **Docs** | https://api-docs.igdb.com/#getting-started |
| **Overview** | https://www.igdb.com/api |
| **Signup** | Twitch Developer → Client ID + OAuth access token |
| **Cost** | **Free for non-commercial** use (Twitch Developer Service Agreement); commercial → partner@igdb.com |
| **Protocol** | `POST https://api.igdb.com/v4/{endpoint}` + `Client-ID` + `Authorization: Bearer` |
| **Platforms** | `POST /v4/platforms` — **~220 platforms** (generations, handhelds, PC, etc.) |
| **Platform structure** | `platform_family`, `platform_type`, `generation`, `platform_version` (hardware revisions where applicable) |
| **Games** | Filter with `where platforms = (id)` or `platforms = {id1,id2}` |
| **PC / Steam** | PC is platform **6** (Microsoft Windows). **Steam** is not always a “platform” row; link via `/external_games` (`external_game_source` = Steam) and `/websites` (category steam) |
| **Stores** | `/external_games` maps Steam app id, GOG, Epic, Xbox marketplace, PlayStation store, etc. |

**Reference: common IGDB platform IDs** (confirm via `/platforms` before production):

| ID | Platform |
|----|----------|
| 6 | PC (Microsoft Windows) |
| 7 | PlayStation |
| 8 | PlayStation 2 |
| 9 | PlayStation 3 |
| 38 | PlayStation Portable |
| 46 | PlayStation Vita |
| 48 | PlayStation 4 |
| 165 | PlayStation VR |
| 167 | PlayStation 5 |
| 11 | Xbox |
| 12 | Xbox 360 |
| 49 | Xbox One |
| 169 | Xbox Series X\|S |
| 130 | Nintendo Switch |
| 18 | Nintendo Entertainment System |
| 19 | Super Nintendo |
| 21 | Nintendo GameCube |
| 41 | Wii U |
| 5 | Wii |
| 37 | Nintendo 3DS |
| 20 | Nintendo DS |
| 34 | Android |
| 39 | iOS |
| 92 | SteamOS |
| 163 | SteamVR |

Community ID lists: [tonkatsu-collections IGDB platform reference](https://github.com/hacan359/tonkatsu-collections/commit/776c3d9fbac39758c83ed482bbcc93e06bedcf3b) (verify against live API).

**Cross-linking Steam ↔ IGDB:** use `/external_games` with `uid` = Steam `appid` and `external_game_source` for Steam — see [Stack Overflow: Steam + IGDB](https://stackoverflow.com/questions/64824485/synchronize-data-from-steam-api-and-igdb).

**OpenAPI (platforms):** [IGDB platforms OpenAPI](https://raw.githubusercontent.com/api-evangelist/igdb/refs/heads/main/openapi/igdb-platforms-api-openapi.yml)

**Example (conceptual):** all PS3 games with ratings:

```text
POST /v4/games
fields name,genres,total_rating,platforms;
where platforms = (9) & total_rating > 0;
sort total_rating desc;
limit 50;
```

---

### 2. RAWG — simple REST, parent + child platforms

| | |
|---|---|
| **Docs** | https://rawg.io/apidocs |
| **Cost** | Free with **attribution**; commercial limits on MAU/page views (see site) |
| **Protocol** | `GET https://api.rawg.io/api/...?key=YOUR_KEY` |
| **List platforms** | `GET /api/platforms` |
| **Parent families** | `GET /api/platforms/lists/parents` — e.g. **PlayStation** groups PS1, PS2, PS3, PS4, PS5 |
| **Platform detail** | `GET /api/platforms/{id}` |
| **Games by platform** | `GET /api/games?platforms={id1},{id2}` (+ dates, ordering, Metacritic) |
| **Steam signal** | Player activity / Steam playtime fields where available (see docs) |

**OpenAPI:** [RAWG platforms API](https://raw.githubusercontent.com/api-evangelist/rawg/refs/heads/main/openapi/rawg-platforms-api-openapi.yml)

**Note:** Platform numeric IDs are **RAWG-specific** — always fetch `/platforms` and store your own mapping table; do not hardcode IGDB IDs into RAWG queries.

**Scalar reference:** https://rawg.apidocumentation.com/version-0/reference

---

### 3. Steam (Valve) — PC catalog depth; pair with IGDB/RAWG for consoles

Steam is a **store**, not a full multi-console DB. Use for **PC / Steam** titles, prices, reviews, tags.

| Endpoint | Purpose | Docs |
|----------|---------|------|
| **IStoreService/GetAppList** | Paginated full store app list (replaces deprecated `ISteamApps/GetAppList`) | [IStoreService](https://partner.steamgames.com/doc/webapi/IStoreService) |
| **store.steampowered.com/api/appdetails** | Per-app metadata, tags, Metacritic, descriptions | Community standard; rate-limit carefully |
| **appreviews** | User reviews | Used in research datasets |
| **Steam Web API key** | Required for official Web API calls | https://steamcommunity.com/dev/apikey |

**Important:**

- `ISteamApps/GetAppList/v2` is **deprecated** at scale — use **IStoreService/GetAppList** ([Steamworks ISteamApps](https://partner.steamgames.com/doc/webapi/ISteamApps)).
- Match Steam `appid` to global game records via **IGDB `external_games`** or manual mapping.

**Research dataset (not live API):** [Steam Dataset 2025](https://github.com/vintagedon/steam-dataset-2025) — bulk snapshot; good for ML/offline analysis, not a substitute for live sync.

---

## Secondary / enrichment sources

### GameBrain API

| | |
|---|---|
| **URL** | https://gamebrain.co/api |
| **Coverage** | 70+ platforms including `playstation_5`, PC, Xbox Series, etc. |
| **Cost** | Free tier (API key; backlink may be required) |
| **Detail** | https://gamebrain.co/api/docs/game-detail |

---

### Metacritic (unofficial JSON backend)

| | |
|---|---|
| **Official API** | None |
| **Unofficial** | `backend.metacritic.com` (website backend; community-documented) |
| **Data** | Metascore + user score; **per-platform** scores on some titles |
| **Not provided** | Storyline / graphics / action breakdown |
| **References** | [metacritic-backend-scraper](https://github.com/davutbayik/metacritic-backend-scraper), [metacritic-ts](https://github.com/Deadlock-too/metacritic-ts) |

Use with rate limits and legal/ToS review.

---

### PlayStation Store (scraping)

| | |
|---|---|
| **Use** | Sony-first catalog, store star ratings, PS4/PS5 SKUs |
| **Reference** | [ps-rating-scraper](https://github.com/Klohto/ps-rating-scraper) |
| **Managed scraper (paid)** | [Apify PlayStation scraper](https://apify.com/easyapi/playstation-games-scraper/api) |

Complements IGDB/RAWG; does not replace Xbox/Steam data.

---

### MobyGames API (subscription; research waiver possible)

| | |
|---|---|
| **Docs** | https://www.mobygames.com/info/api/ |
| **Subscribe** | https://www.mobygames.com/api/subscribe/ |
| **Strength** | **Per-game, per-platform** releases; Moby Score; critic/player scores on paid tiers |
| **Free** | Hobbyist paid tier; **non-commercial research** may request free access via their form |

Good when you need explicit **“this game on PS2 vs PS3”** release rows.

---

### OpenVGDB (free download; retro / ROM-oriented)

| | |
|---|---|
| **Releases** | https://github.com/OpenVGDB/OpenVGDB/releases |
| **Format** | SQLite / dumps — not a hosted REST API |
| **Coverage** | Strong on **older consoles** (NES, SNES, N64, etc.); not a full modern PS5/Xbox live feed |

Useful as a **static supplement** for legacy platforms.

---

## Sources not available or not recommended as primary

| Source | Status |
|--------|--------|
| **Giant Bomb API** | **Not currently available** after site migration; wiki rebuild in progress — https://giantbomb.com/api |
| **Wikipedia / Wikidata** | Sparse ratings; OK for identifiers, not for recommender scores |
| **Kaggle-only dumps** | Bootstrap only; stale for “latest on PS5 / Steam” |

---

## Suggested data model (multi-platform)

```text
platform_family     (PlayStation, Xbox, Nintendo, PC, …)
platform            (PS3, Xbox One, Steam-as-distribution, Switch, …)
game                (canonical title)
game_platform       (game_id, platform_id, release_date, store_url, scores)
genre / game_genre
external_id         (source, external_id)  -- igdb_id, rawg_id, steam_appid, …
```

**User asks:** “Good RPGs on **PS2**” → filter `platform.slug = ps2` (your normalized id) → genre → sort by chosen dimension.

**User asks:** “On **Steam**” → filter PC releases linked to `steam_appid` or platform = PC + store = Steam.

---

## Rating dimensions (storyline, graphics, action)

Free catalogs usually provide **overall** scores (user, critic, blended) and **genres/themes**, not separate storyline/graphics/action API fields.

| User dimension | MVP ranking approach |
|----------------|----------------------|
| Overall | `total_rating`, Metacritic, or Moby Score |
| Story / storyline | Narrative genres/themes + high critic score |
| Graphics | High critic score on AAA/visual tags; optional manual tier |
| Action | Action/Shooter genre + rating |
| RPG | Role-playing genre + rating |

**Later:** NLP on reviews (Steam, Metacritic) or TypeSafe judgments to derive aspect scores.

---

## Recommended ingest strategy (multi-platform)

| Priority | Source | Role |
|----------|--------|------|
| 1 | **IGDB** *or* **RAWG** | Canonical games, **all major platforms**, genres, core ratings |
| 2 | **Steam Web API + appdetails** | Enrich **PC/Steam** library and live store fields |
| 3 | **Metacritic** (optional) | Critic/user scores per title/platform |
| 4 | **PlayStation scraper** (optional) | Sony store-specific list/ratings |
| 5 | **MobyGames** (optional) | Per-platform release granularity |
| 6 | **OpenVGDB** (optional) | Legacy console backfill |

1. Sync **`/platforms`** (and RAWG parent platforms) into `platform` + `platform_family`.
2. For each supported platform id, paginate games into `game` + `game_platform`.
3. Join **Steam appids** via IGDB `external_games`.
4. Agent tools query **only your DB** with `(platform_id, genre, sort_dimension)`.

---

## Compliance checklist

- [ ] IGDB: non-commercial vs commercial use
- [ ] RAWG / GameBrain: **attribution** and plan limits
- [ ] Steam: [Steam Web API terms](https://steamcommunity.com/dev/apikey)
- [ ] Scraping: rate limits and site ToS
- [ ] Store `data_source`, `external_ids`, and `last_synced_at` on every row

---

## Next steps

1. Pick **IGDB vs RAWG** as primary (IGDB is stronger for **store cross-refs**; RAWG is simpler REST).
2. Define **supported platform list** (e.g. PS1–PS5, Xbox 360/One/Series, PC/Steam, Switch).
3. Build **platform id mapping table** (IGDB id ↔ RAWG id ↔ internal slug).
4. Implement sync jobs + `recommend_games(platform, genre, sort_by)` API for the LiveKit agent.
