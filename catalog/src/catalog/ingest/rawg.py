"""Ingest game catalog from RAWG. https://rawg.io/apidocs"""

from __future__ import annotations

import json
import os
import subprocess
import time
from urllib.parse import urlencode, urlparse, parse_qs

from sqlalchemy import select
from sqlalchemy.orm import Session

from catalog.ingest.repository import parse_release_date, upsert_game_with_rag
from catalog.ingest.runner import ingestion_run
from catalog.ingest.util import build_rag_document, slugify
from catalog.models import Genre, Platform, PlatformFamily

RAWG_API_BASE = "https://api.rawg.io/api"

# RAWG platform ids (verify via GET /api/platforms) — modern consoles + PC
DEFAULT_RAWG_PLATFORM_IDS: tuple[int, ...] = (
    187,  # PlayStation 5
    18,   # PlayStation 4
    16,   # PlayStation 3
    15,   # PlayStation 2
    27,   # PlayStation
    186,  # Xbox Series S/X
    1,    # Xbox One
    14,   # Xbox 360
    7,    # Nintendo Switch
    4,    # PC
    8,    # Nintendo 3DS
    9,    # Nintendo DS
    17,   # PSP
    19,   # PS Vita
)

FAMILY_FROM_SLUG: dict[str, str] = {
    "playstation": "playstation",
    "xbox": "xbox",
    "nintendo": "nintendo",
    "pc": "pc",
    "ios": "mobile",
    "android": "mobile",
    "mac": "pc",
    "linux": "pc",
}


def get_rawg_api_key() -> str:
    key = os.getenv("RAWG_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing RAWG_API_KEY in .env.local")
    return key


class RAWGClient:
    def __init__(self, api_key: str, *, delay_seconds: float = 0.35):
        self.api_key = api_key
        self.delay_seconds = delay_seconds

    def get(self, path: str, params: dict | None = None) -> dict:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        params = dict(params or {})
        params["key"] = self.api_key
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{RAWG_API_BASE}{path}?{urlencode(params)}"
        result = subprocess.run(
            ["curl", "-fsSL", "-A", "voice-agent-catalog/0.1", url],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            raise RuntimeError(f"RAWG GET {path} failed: {result.stderr or result.stdout}")
        return json.loads(result.stdout)

    def get_url(self, url: str) -> dict:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "key" not in qs:
            sep = "&" if parsed.query else "?"
            url = f"{url}{sep}key={self.api_key}"
        result = subprocess.run(
            ["curl", "-fsSL", "-A", "voice-agent-catalog/0.1", url],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            raise RuntimeError(f"RAWG GET url failed: {result.stderr or result.stdout}")
        return json.loads(result.stdout)


def _infer_family_slug(platform_slug: str, platform_name: str) -> str:
    hay = f"{platform_slug} {platform_name}".lower()
    for needle, family in FAMILY_FROM_SLUG.items():
        if needle in hay:
            return family
    return "other"


def upsert_platform_rawg(session: Session, row: dict, stats: dict) -> Platform:
    rawg_id = int(row["id"])
    platform = session.scalar(select(Platform).where(Platform.rawg_id == rawg_id))
    slug = (row.get("slug") or slugify(row.get("name") or f"rawg-{rawg_id}"))[:120]
    name = row.get("name") or slug
    family_slug = _infer_family_slug(slug, name)

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
        platform.rawg_id = rawg_id
        stats["platforms_updated"] = stats.get("platforms_updated", 0) + 1
        return platform

    by_slug = session.scalar(select(Platform).where(Platform.slug == slug))
    if by_slug:
        by_slug.rawg_id = rawg_id
        by_slug.name = name
        stats["platforms_updated"] = stats.get("platforms_updated", 0) + 1
        return by_slug

    platform = Platform(
        slug=slug,
        name=name,
        family_id=family.id,
        rawg_id=rawg_id,
    )
    session.add(platform)
    session.flush()
    stats["platforms_inserted"] = stats.get("platforms_inserted", 0) + 1
    return platform


def sync_rawg_platforms(
    session: Session, client: RAWGClient, platform_ids: tuple[int, ...], stats: dict
) -> dict[int, Platform]:
    by_rawg: dict[int, Platform] = {}
    for pid in platform_ids:
        row = client.get(f"/platforms/{pid}")
        platform = upsert_platform_rawg(session, row, stats)
        by_rawg[pid] = platform
    session.commit()
    return by_rawg


def sync_rawg_genres(session: Session, client: RAWGClient, stats: dict) -> None:
    page = 1
    total = 0
    while True:
        payload = client.get("/genres", {"page": page, "page_size": 40})
        results = payload.get("results") or []
        if not results:
            break
        for row in results:
            rawg_id = int(row["id"])
            name = row.get("name") or row.get("slug")
            slug = row.get("slug") or slugify(name or f"genre-{rawg_id}")
            genre = session.scalar(select(Genre).where(Genre.rawg_id == rawg_id))
            if genre:
                genre.name = name
                genre.slug = slug
            else:
                existing = session.scalar(select(Genre).where(Genre.slug == slug))
                if existing:
                    existing.rawg_id = rawg_id
                    existing.name = name
                else:
                    session.add(Genre(slug=slug, name=name, rawg_id=rawg_id))
            total += 1
        if not payload.get("next"):
            break
        page += 1
    session.commit()
    stats["genres_synced"] = total


def _genre_labels(game: dict) -> list[str]:
    labels: list[str] = []
    for g in game.get("genres") or []:
        if isinstance(g, dict) and g.get("name"):
            labels.append(str(g["name"]))
    return labels


def ingest_games_for_rawg_platform(
    session: Session,
    client: RAWGClient,
    *,
    platform: Platform,
    rawg_platform_id: int,
    games_limit: int,
    page_size: int,
    stats: dict,
) -> None:
    imported = 0
    page = 1
    next_url: str | None = None

    while imported < games_limit:
        if next_url:
            payload = client.get_url(next_url)
        else:
            payload = client.get(
                "/games",
                {
                    "platforms": rawg_platform_id,
                    "ordering": "-metacritic",
                    "page": page,
                    "page_size": min(page_size, games_limit - imported),
                },
            )

        results = payload.get("results") or []
        if not results:
            break

        for game in results:
            if imported >= games_limit:
                break
            rawg_game_id = int(game["id"])
            title = (game.get("name") or "").strip()
            if not title:
                continue

            genres = _genre_labels(game)
            description = (game.get("description_raw") or game.get("description") or "").strip()
            summary = description[:4000] if description else None

            rawg_rating = game.get("rating")
            rating_user = None
            if rawg_rating is not None:
                try:
                    rating_user = float(rawg_rating) * 20.0
                except (TypeError, ValueError):
                    rating_user = None

            metacritic = game.get("metacritic")
            rating_total = None
            if metacritic is not None:
                try:
                    rating_total = float(metacritic)
                except (TypeError, ValueError):
                    rating_total = rating_user
            else:
                rating_total = rating_user

            released = game.get("released")
            store_url = game.get("website") or None

            rag = build_rag_document(
                title=title,
                platform_name=platform.name,
                summary=summary,
                genres=genres,
                extra=(
                    f"RAWG rating: {rawg_rating}/5; Metacritic: {metacritic}"
                    if rawg_rating is not None or metacritic is not None
                    else None
                ),
            )

            rawg_rating_val = None
            if rawg_rating is not None:
                try:
                    rawg_rating_val = float(rawg_rating)
                except (TypeError, ValueError):
                    rawg_rating_val = None

            upsert_game_with_rag(
                session,
                source="rawg",
                external_id=str(rawg_game_id),
                title=title,
                platform=platform,
                summary=summary,
                release_date=parse_release_date(str(released)) if released else None,
                store_url=store_url,
                genre_labels=genres,
                rating_user=rating_user,
                rating_critic=rating_total,
                rating_total=rating_total,
                metacritic_score=int(metacritic) if metacritic is not None else None,
                rawg_rating=rawg_rating_val,
                rag_document=rag,
                chunk_metadata={
                    "source": "rawg",
                    "rawg_game_id": rawg_game_id,
                    "rawg_platform_id": rawg_platform_id,
                },
                stats=stats,
            )
            imported += 1

        next_url = payload.get("next")
        if not next_url:
            break
        page += 1

    stats.setdefault("games_by_platform", {})[str(rawg_platform_id)] = imported


def ingest_rawg(
    session: Session,
    *,
    platform_ids: tuple[int, ...] | None = None,
    games_per_platform: int = 100,
    page_size: int = 40,
    delay_seconds: float = 0.35,
    sync_genres: bool = True,
) -> dict:
    platform_ids = platform_ids or DEFAULT_RAWG_PLATFORM_IDS
    client = RAWGClient(get_rawg_api_key(), delay_seconds=delay_seconds)

    with ingestion_run(session, "rawg") as stats:
        stats["platform_ids"] = list(platform_ids)
        stats["games_per_platform"] = games_per_platform

        platforms = sync_rawg_platforms(session, client, platform_ids, stats)
        if sync_genres:
            sync_rawg_genres(session, client, stats)

        for rawg_pid in platform_ids:
            platform = platforms.get(rawg_pid)
            if not platform:
                stats.setdefault("platforms_missing", []).append(rawg_pid)
                continue
            ingest_games_for_rawg_platform(
                session,
                client,
                platform=platform,
                rawg_platform_id=rawg_pid,
                games_limit=games_per_platform,
                page_size=page_size,
                stats=stats,
            )
            session.commit()

    return stats
