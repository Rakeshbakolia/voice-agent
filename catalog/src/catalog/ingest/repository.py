from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from catalog.ingest.util import build_rag_document, slugify, unique_slug
from catalog.models import (
    Game,
    GameChunk,
    GameExternalId,
    GameGenre,
    GamePlatform,
    Genre,
    Platform,
    PlatformFamily,
)


def get_or_create_platform_family(session: Session, slug: str, name: str) -> PlatformFamily:
    row = session.scalar(select(PlatformFamily).where(PlatformFamily.slug == slug))
    if row:
        return row
    row = PlatformFamily(slug=slug, name=name)
    session.add(row)
    session.flush()
    return row


def get_or_create_platform(
    session: Session,
    *,
    slug: str,
    name: str,
    family_slug: str,
    family_name: str | None = None,
    generation: int | None = None,
) -> Platform:
    row = session.scalar(select(Platform).where(Platform.slug == slug))
    if row:
        return row
    family = get_or_create_platform_family(
        session, family_slug, family_name or family_slug.replace("-", " ").title()
    )
    row = Platform(
        slug=slug,
        name=name,
        family_id=family.id,
        generation=generation,
    )
    session.add(row)
    session.flush()
    return row


def get_or_create_genre(session: Session, label: str) -> Genre:
    slug = slugify(label)
    row = session.scalar(select(Genre).where(Genre.slug == slug))
    if row:
        return row
    row = Genre(slug=slug, name=label)
    session.add(row)
    session.flush()
    return row


def find_game_by_external_id(
    session: Session, source: str, external_id: str
) -> Game | None:
    link = session.scalar(
        select(GameExternalId).where(
            GameExternalId.source == source,
            GameExternalId.external_id == external_id,
        )
    )
    if not link:
        return None
    return session.get(Game, link.game_id)


def upsert_game_with_rag(
    session: Session,
    *,
    source: str,
    external_id: str,
    title: str,
    platform: Platform,
    summary: str | None,
    storyline: str | None = None,
    release_date: date | None,
    store_url: str | None,
    genre_labels: Iterable[str],
    rating_user: float | None = None,
    rating_critic: float | None = None,
    rating_total: float | None = None,
    metacritic_score: int | None = None,
    rawg_rating: float | None = None,
    rag_document: str,
    chunk_metadata: dict,
    stats: dict,
) -> Game:
    game = find_game_by_external_id(session, source, external_id)
    created = game is None
    slug_base = unique_slug(title, platform.slug)

    if created:
        slug = slug_base
        counter = 1
        while session.scalar(select(Game.id).where(Game.slug == slug)):
            slug = unique_slug(f"{slug_base}-{counter}", platform.slug)
            counter += 1
        game = Game(slug=slug, name=title, summary=summary, storyline=storyline)
        session.add(game)
        session.flush()
        session.add(
            GameExternalId(game_id=game.id, source=source, external_id=external_id)
        )
        stats["games_inserted"] = stats.get("games_inserted", 0) + 1
    else:
        game.name = title
        if summary:
            game.summary = summary
        if storyline:
            game.storyline = storyline
        stats["games_updated"] = stats.get("games_updated", 0) + 1

    now = datetime.now(timezone.utc)
    gp = session.get(GamePlatform, (game.id, platform.id))
    if not gp:
        gp = GamePlatform(game_id=game.id, platform_id=platform.id)
        session.add(gp)
    gp.release_date = release_date
    gp.store_url = store_url
    gp.rating_user = rating_user
    gp.rating_critic = rating_critic
    gp.rating_total = rating_total
    gp.metacritic_score = metacritic_score
    if rawg_rating is not None:
        gp.rawg_rating = rawg_rating
    gp.last_synced_at = now
    gp.source = source

    existing_genres = {
        gg.genre_id
        for gg in session.scalars(
            select(GameGenre).where(GameGenre.game_id == game.id)
        )
    }
    for label in genre_labels:
        genre = get_or_create_genre(session, label)
        if genre.id not in existing_genres:
            session.add(GameGenre(game_id=game.id, genre_id=genre.id))
            existing_genres.add(genre.id)

    chunk = session.scalar(
        select(GameChunk).where(
            GameChunk.game_id == game.id,
            GameChunk.platform_id == platform.id,
            GameChunk.chunk_index == 0,
        )
    )
    if not chunk:
        chunk = GameChunk(
            game_id=game.id,
            platform_id=platform.id,
            chunk_index=0,
            content=rag_document,
            metadata_=chunk_metadata,
        )
        session.add(chunk)
        stats["chunks_inserted"] = stats.get("chunks_inserted", 0) + 1
    else:
        chunk.content = rag_document
        chunk.metadata_ = {**chunk.metadata_, **chunk_metadata}
        stats["chunks_updated"] = stats.get("chunks_updated", 0) + 1

    return game


def parse_release_date(raw: str | None) -> date | None:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d %b, %Y", "%d %B, %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    year_match = re.search(r"(19|20)\d{2}", raw)
    if year_match:
        return date(int(year_match.group(0)), 1, 1)
    return None
