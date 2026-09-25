"""Ingest game catalog from IGDB (Twitch API). https://api-docs.igdb.com/"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from catalog.ingest.repository import upsert_game_with_rag
from catalog.ingest.runner import ingestion_run
from catalog.ingest.twitch import get_app_access_token
from catalog.ingest.util import build_rag_document, slugify
from catalog.models import Genre, Platform, PlatformFamily

IGDB_BASE = "https://api.igdb.com/v4"

# IGDB platform ids — modern + common (see game-data-sources.md)
DEFAULT_IGDB_PLATFORM_IDS: tuple[int, ...] = (
    167,  # PlayStation 5
    48,   # PlayStation 4
    9,    # PlayStation 3
    8,    # PlayStation 2
    7,    # PlayStation
    169,  # Xbox Series X|S
    49,   # Xbox One
    12,   # Xbox 360
    11,   # Xbox
    130,  # Nintendo Switch
    6,    # PC (Windows)
    39,   # iOS
    34,   # Android
    38,   # PSP
    46,   # PS Vita
)

FAMILY_SLUG_ALIASES: dict[str, str] = {
    "playstation": "playstation",
    "xbox": "xbox",
    "nintendo": "nintendo",
    "pc": "pc",
    "mac": "pc",
    "linux": "pc",
    "ios": "mobile",
    "android": "mobile",
}


class IGDBClient:
    def __init__(self, client_id: str, access_token: str, *, delay_seconds: float = 0.26):
        self.client_id = client_id
        self.access_token = access_token
        self.delay_seconds = delay_seconds

    def query(self, endpoint: str, body: str) -> list[dict]:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "-X",
                "POST",
                f"{IGDB_BASE}/{endpoint}",
                "-H",
                f"Client-ID: {self.client_id}",
                "-H",
                f"Authorization: Bearer {self.access_token}",
                "-H",
                "Accept: application/json",
                "-d",
                body,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"IGDB {endpoint} failed: {result.stderr or result.stdout}"
            )
        text = result.stdout.strip()
        if not text:
            return []
        data = json.loads(text)
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected IGDB response for {endpoint}: {data!r}")
        return data


def _family_slug_from_igdb(family: dict | None) -> str:
    if not family:
        return "other"
    raw = (family.get("slug") or family.get("name") or "").lower()
    for needle, slug in FAMILY_SLUG_ALIASES.items():
        if needle in raw:
            return slug
    return "other"


def _igdb_unix_to_date(value: int | None) -> date | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).date()


def _normalize_rating(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def upsert_platform_row(session: Session, row: dict, stats: dict) -> Platform:
    igdb_id = int(row["id"])
    platform = session.scalar(select(Platform).where(Platform.igdb_id == igdb_id))
    slug = (row.get("slug") or slugify(row.get("name") or f"igdb-{igdb_id}"))[:120]
    name = row.get("name") or slug
    generation = row.get("generation")
    family_info = row.get("platform_family")
    if isinstance(family_info, int):
        family_slug = "other"
    else:
        family_slug = _family_slug_from_igdb(family_info if isinstance(family_info, dict) else None)

    family = session.scalar(select(PlatformFamily).where(PlatformFamily.slug == family_slug))
    if not family:
        family = PlatformFamily(
            slug=family_slug,
            name=family_slug.replace("-", " ").title(),
        )
        session.add(family)
        session.flush()

    if platform:
        platform.name = name
        platform.slug = platform.slug or slug
        platform.generation = generation
        if platform.family_id is None:
            platform.family_id = family.id
        stats["platforms_updated"] = stats.get("platforms_updated", 0) + 1
        return platform

    existing_slug = session.scalar(select(Platform).where(Platform.slug == slug))
    if existing_slug:
        existing_slug.igdb_id = igdb_id
        existing_slug.name = name
        existing_slug.generation = generation
        stats["platforms_updated"] = stats.get("platforms_updated", 0) + 1
        return existing_slug

    platform = Platform(
        slug=slug,
        name=name,
        family_id=family.id,
        generation=generation,
        igdb_id=igdb_id,
    )
    session.add(platform)
    session.flush()
    stats["platforms_inserted"] = stats.get("platforms_inserted", 0) + 1
    return platform


def sync_igdb_platforms(
    session: Session, client: IGDBClient, igdb_platform_ids: tuple[int, ...], stats: dict
) -> dict[int, Platform]:
    id_list = ",".join(str(i) for i in igdb_platform_ids)
    body = (
        "fields id,name,slug,generation,platform_family.slug,platform_family.name;"
        f"where id = ({id_list});"
        f"limit {len(igdb_platform_ids)};"
    )
    rows = client.query("platforms", body)
    by_igdb: dict[int, Platform] = {}
    for row in rows:
        platform = upsert_platform_row(session, row, stats)
        by_igdb[int(row["id"])] = platform
    session.commit()
    return by_igdb


def sync_igdb_genres(session: Session, client: IGDBClient, stats: dict) -> dict[int, str]:
    rows = client.query("genres", "fields id,name,slug; limit 500;")
    names: dict[int, str] = {}
    for row in rows:
        igdb_id = int(row["id"])
        name = row.get("name") or row.get("slug") or f"genre-{igdb_id}"
        slug = row.get("slug") or slugify(name)
        genre = session.scalar(select(Genre).where(Genre.igdb_id == igdb_id))
        if genre:
            genre.name = name
            genre.slug = slug
        else:
            existing = session.scalar(select(Genre).where(Genre.slug == slug))
            if existing:
                existing.igdb_id = igdb_id
                existing.name = name
                genre = existing
            else:
                genre = Genre(slug=slug, name=name, igdb_id=igdb_id)
                session.add(genre)
        names[igdb_id] = name
    session.commit()
    stats["genres_synced"] = len(names)
    return names


def _genre_labels_from_game(game_row: dict) -> list[str]:
    genres = game_row.get("genres") or []
    labels: list[str] = []
    for g in genres:
        if isinstance(g, dict) and g.get("name"):
            labels.append(str(g["name"]))
    return labels


def ingest_games_for_igdb_platform(
    session: Session,
    client: IGDBClient,
    *,
    platform: Platform,
    igdb_platform_id: int,
    games_limit: int,
    page_size: int,
    stats: dict,
) -> None:
    offset = 0
    imported = 0
    while imported < games_limit:
        batch = min(page_size, games_limit - imported)
        body = (
            "fields id,name,summary,storyline,slug,genres.name,"
            "aggregated_rating,rating,total_rating,first_release_date;"
            f"where platforms = ({igdb_platform_id}) & total_rating > 0;"
            f"sort total_rating desc;"
            f"limit {batch}; offset {offset};"
        )
        games = client.query("games", body)
        if not games:
            break

        for game_row in games:
            igdb_game_id = int(game_row["id"])
            title = (game_row.get("name") or "").strip()
            if not title:
                continue

            summary = (game_row.get("summary") or "").strip() or None
            storyline = (game_row.get("storyline") or "").strip() or None
            genres = _genre_labels_from_game(game_row)
            rating_critic = _normalize_rating(game_row.get("aggregated_rating"))
            rating_user = _normalize_rating(game_row.get("rating"))
            rating_total = _normalize_rating(game_row.get("total_rating"))

            rag = build_rag_document(
                title=title,
                platform_name=platform.name,
                summary=summary,
                genres=genres,
                extra=(
                    f"IGDB ratings (0-100): total={rating_total}, "
                    f"critic={rating_critic}, user={rating_user}"
                    if rating_total is not None
                    else None
                ),
            )
            if storyline:
                rag = f"{rag}\nStoryline: {storyline[:4000]}"

            upsert_game_with_rag(
                session,
                source="igdb",
                external_id=str(igdb_game_id),
                title=title,
                platform=platform,
                summary=summary,
                storyline=storyline,
                release_date=_igdb_unix_to_date(game_row.get("first_release_date")),
                store_url=None,
                genre_labels=genres,
                rating_user=rating_user,
                rating_critic=rating_critic,
                rating_total=rating_total,
                rag_document=rag,
                chunk_metadata={
                    "source": "igdb",
                    "igdb_game_id": igdb_game_id,
                    "igdb_platform_id": igdb_platform_id,
                },
                stats=stats,
            )
            imported += 1

        offset += len(games)
        if len(games) < batch:
            break

    stats.setdefault("games_by_platform", {})[str(igdb_platform_id)] = imported


def ingest_igdb(
    session: Session,
    *,
    platform_ids: tuple[int, ...] | None = None,
    games_per_platform: int = 100,
    page_size: int = 50,
    delay_seconds: float = 0.26,
    sync_genres: bool = True,
) -> dict:
    platform_ids = platform_ids or DEFAULT_IGDB_PLATFORM_IDS
    token, client_id = get_app_access_token()
    client = IGDBClient(client_id, token, delay_seconds=delay_seconds)

    with ingestion_run(session, "igdb") as stats:
        stats["platform_ids"] = list(platform_ids)
        stats["games_per_platform"] = games_per_platform

        platforms = sync_igdb_platforms(session, client, platform_ids, stats)
        if sync_genres:
            sync_igdb_genres(session, client, stats)

        for igdb_pid in platform_ids:
            platform = platforms.get(igdb_pid)
            if not platform:
                stats.setdefault("platforms_missing", []).append(igdb_pid)
                continue
            ingest_games_for_igdb_platform(
                session,
                client,
                platform=platform,
                igdb_platform_id=igdb_pid,
                games_limit=games_per_platform,
                page_size=page_size,
                stats=stats,
            )
            session.commit()

    return stats
