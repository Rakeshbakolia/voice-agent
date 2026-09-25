"""Read-only queries for voice-agent game recommendations."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from catalog.models import Game, GameChunk, GameGenre, GamePlatform, Genre, Platform

SortDimension = Literal["total", "critic", "user", "story", "graphics", "action"]

_PLATFORM_ALIASES: dict[str, tuple[str, ...]] = {
    "ps5": ("ps5", "playstation5"),
    "playstation-5": ("ps5", "playstation5"),
    "playstation 5": ("ps5", "playstation5"),
    "ps4": ("ps4", "playstation4"),
    "playstation-4": ("ps4", "playstation4"),
    "ps3": ("ps3", "playstation3"),
    "ps2": ("ps2", "playstation2"),
    "ps1": ("ps1", "playstation1"),
    "xbox-series-x": ("xbox-series-x", "xbox-series"),
    "xbox-series-s": ("xbox-series-x", "xbox-series"),
    "xbox-one": ("xbox-one",),
    "xbox-360": ("xbox-360",),
    "switch": ("nintendo-switch",),
    "nintendo-switch": ("nintendo-switch",),
    "pc": ("pc-windows", "pc"),
    "steam": ("pc-windows", "pc"),
    "windows": ("pc-windows",),
}

_GENRE_ALIASES: dict[str, tuple[str, ...]] = {
    "rpg": ("rpg", "role-playing", "role-playing-rpg", "action-rpg"),
    "role-playing": ("role-playing", "rpg", "role-playing-rpg"),
    "fps": ("shooter",),
    "shooter": ("shooter",),
}


def _normalize_token(value: str) -> str:
    return re.sub(r"\s+", "-", value.strip().lower())


def resolve_platform_slugs(platform: str) -> tuple[str, ...]:
    key = _normalize_token(platform)
    if key in _PLATFORM_ALIASES:
        return _PLATFORM_ALIASES[key]
    return (key,)


def resolve_genre_slugs(genre: str) -> tuple[str, ...]:
    key = _normalize_token(genre)
    if key in _GENRE_ALIASES:
        return _GENRE_ALIASES[key]
    return (key,)


def _rating_column(sort_by: SortDimension):
    return {
        "total": GamePlatform.rating_total,
        "critic": GamePlatform.rating_critic,
        "user": GamePlatform.rating_user,
        "story": GamePlatform.rating_story,
        "graphics": GamePlatform.rating_graphics,
        "action": GamePlatform.rating_action,
    }[sort_by]


def _platform_rating(gp: GamePlatform, sort_by: SortDimension) -> Optional[float]:
    if sort_by == "total":
        return gp.rating_total
    if sort_by == "critic":
        return gp.rating_critic
    if sort_by == "user":
        return gp.rating_user
    if sort_by == "story":
        return gp.rating_story
    if sort_by == "graphics":
        return gp.rating_graphics
    return gp.rating_action


def _genre_names_for_game(session: Session, game_id: uuid.UUID) -> tuple[str, ...]:
    names = session.scalars(
        select(Genre.name)
        .join(GameGenre, GameGenre.genre_id == Genre.id)
        .where(GameGenre.game_id == game_id)
    ).all()
    return tuple(sorted(names))


@dataclass(frozen=True)
class GameSearchHit:
    game_id: uuid.UUID
    name: str
    platform_name: str
    platform_slug: str
    rating: Optional[float]
    summary: Optional[str]
    genres: tuple[str, ...]


def _load_platform_ids(session: Session, platform: str) -> list[int]:
    slugs = resolve_platform_slugs(platform)
    rows = session.scalars(select(Platform).where(Platform.slug.in_(slugs))).all()
    if rows:
        return [p.id for p in rows]
    token = _normalize_token(platform)
    fuzzy = session.scalars(
        select(Platform).where(
            or_(
                Platform.slug.ilike(f"%{token}%"),
                Platform.name.ilike(f"%{platform.strip()}%"),
            )
        )
    ).all()
    return [p.id for p in fuzzy[:5]]


def _load_genre_ids(session: Session, genre: str) -> list[int]:
    slugs = resolve_genre_slugs(genre)
    rows = session.scalars(select(Genre).where(Genre.slug.in_(slugs))).all()
    if rows:
        return [g.id for g in rows]
    token = _normalize_token(genre)
    fuzzy = session.scalars(
        select(Genre).where(
            or_(Genre.slug.ilike(f"%{token}%"), Genre.name.ilike(f"%{genre.strip()}%"))
        )
    ).all()
    return [g.id for g in fuzzy[:8]]


def search_games(
    session: Session,
    *,
    platform: str,
    genre: Optional[str] = None,
    sort_by: SortDimension = "total",
    limit: int = 5,
    min_rating: Optional[float] = None,
    require_rating: bool = True,
) -> list[GameSearchHit]:
    """Top games on a platform, optionally filtered by genre."""
    limit = max(1, min(limit, 15))
    platform_ids = _load_platform_ids(session, platform)
    if not platform_ids:
        return []

    rating_col = _rating_column(sort_by)
    stmt: Select = (
        select(Game, GamePlatform, Platform)
        .join(GamePlatform, GamePlatform.game_id == Game.id)
        .join(Platform, Platform.id == GamePlatform.platform_id)
        .where(GamePlatform.platform_id.in_(platform_ids))
    )

    if genre:
        genre_ids = _load_genre_ids(session, genre)
        if not genre_ids:
            return []
        stmt = stmt.join(GameGenre, GameGenre.game_id == Game.id).where(
            GameGenre.genre_id.in_(genre_ids)
        )

    if min_rating is not None:
        stmt = stmt.where(rating_col >= min_rating)
    elif require_rating:
        stmt = stmt.where(rating_col.is_not(None))

    stmt = stmt.order_by(rating_col.desc().nulls_last(), Game.name).limit(limit * 3)

    seen: set[uuid.UUID] = set()
    hits: list[GameSearchHit] = []
    for game, gp, plat in session.execute(stmt).all():
        if game.id in seen:
            continue
        seen.add(game.id)
        genre_names = _genre_names_for_game(session, game.id)
        hits.append(
            GameSearchHit(
                game_id=game.id,
                name=game.name,
                platform_name=plat.name,
                platform_slug=plat.slug,
                rating=_platform_rating(gp, sort_by),
                summary=game.summary,
                genres=genre_names,
            )
        )
        if len(hits) >= limit:
            break

    return hits


@dataclass(frozen=True)
class GameDetails:
    game_id: uuid.UUID
    name: str
    summary: Optional[str]
    storyline: Optional[str]
    platforms: tuple[str, ...]
    genres: tuple[str, ...]
    best_rating: Optional[float]


def get_game_details(
    session: Session,
    *,
    title: str,
    platform: Optional[str] = None,
) -> Optional[GameDetails]:
    """Case-insensitive title lookup; optional platform scope."""
    name = title.strip()
    if not name:
        return None

    stmt = select(Game).where(func.lower(Game.name) == name.lower())
    game = session.scalar(stmt)
    if game is None:
        game = session.scalar(
            select(Game)
            .where(Game.name.ilike(f"%{name}%"))
            .order_by(func.length(Game.name))
            .limit(1)
        )
    if game is None:
        return None

    platform_ids: Optional[list[int]] = None
    if platform:
        platform_ids = _load_platform_ids(session, platform)
        if not platform_ids:
            return None

    gp_stmt = select(GamePlatform).where(GamePlatform.game_id == game.id)
    if platform_ids:
        gp_stmt = gp_stmt.where(GamePlatform.platform_id.in_(platform_ids))
    game_platforms = session.scalars(gp_stmt.options(joinedload(GamePlatform.platform))).all()

    platform_labels = tuple(sorted({gp.platform.name for gp in game_platforms if gp.platform}))
    ratings = [
        gp.rating_total or gp.rating_critic or gp.metacritic_score
        for gp in game_platforms
        if gp.rating_total or gp.rating_critic or gp.metacritic_score
    ]
    best_rating = max(ratings) if ratings else None

    genre_names = _genre_names_for_game(session, game.id)

    return GameDetails(
        game_id=game.id,
        name=game.name,
        summary=game.summary,
        storyline=game.storyline,
        platforms=platform_labels,
        genres=genre_names,
        best_rating=float(best_rating) if best_rating is not None else None,
    )


def list_supported_filters(session: Session) -> str:
    """Compact platform and genre slugs for tool hints."""
    platforms = session.scalars(select(Platform).order_by(Platform.slug)).all()
    genres = session.scalars(select(Genre).order_by(Genre.name).limit(40)).all()
    plat_line = ", ".join(p.slug for p in platforms[:20])
    genre_line = ", ".join(f"{g.slug}" for g in genres[:25])
    return (
        f"Example platform slugs: {plat_line}. "
        f"Example genre slugs: {genre_line}. "
        "Aliases: ps5, ps4, switch, pc, steam, rpg."
    )


def format_search_results(hits: list[GameSearchHit], *, platform_query: str) -> str:
    if not hits:
        return (
            f"No rated games found for platform '{platform_query}' with those filters. "
            "Try another platform slug like ps5, nintendo-switch, or pc-windows, "
            "or broaden the genre."
        )
    lines = [f"Found {len(hits)} game(s):"]
    for i, h in enumerate(hits, 1):
        rating = f"{h.rating:.0f}" if h.rating is not None else "no score"
        genres = ", ".join(h.genres[:4]) if h.genres else "genres unknown"
        blurb = (h.summary or "")[:160].strip()
        if blurb:
            blurb = f" {blurb}"
        lines.append(
            f"{i}. {h.name} on {h.platform_name}, score {rating}, {genres}.{blurb}"
        )
    return " ".join(lines)


@dataclass(frozen=True)
class SemanticSearchHit:
    game_id: uuid.UUID
    name: str
    platform_name: Optional[str]
    summary: Optional[str]
    snippet: str
    distance: float


def semantic_search_games(
    session: Session,
    query_embedding: list[float],
    *,
    platform: Optional[str] = None,
    limit: int = 5,
) -> list[SemanticSearchHit]:
    """Nearest-neighbor search over embedded ``game_chunk`` rows."""
    limit = max(1, min(limit, 15))
    distance_col = GameChunk.embedding.cosine_distance(query_embedding).label("dist")
    stmt = (
        select(GameChunk, Game, Platform, distance_col)
        .join(Game, Game.id == GameChunk.game_id)
        .outerjoin(Platform, Platform.id == GameChunk.platform_id)
        .where(GameChunk.embedding.is_not(None))
    )
    if platform:
        platform_ids = _load_platform_ids(session, platform)
        if not platform_ids:
            return []
        stmt = stmt.where(GameChunk.platform_id.in_(platform_ids))

    stmt = stmt.order_by(distance_col).limit(limit * 4)

    seen: set[uuid.UUID] = set()
    hits: list[SemanticSearchHit] = []
    for chunk, game, plat, dist in session.execute(stmt).all():
        if game.id in seen:
            continue
        seen.add(game.id)
        snippet = chunk.content.strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        hits.append(
            SemanticSearchHit(
                game_id=game.id,
                name=game.name,
                platform_name=plat.name if plat else None,
                summary=game.summary,
                snippet=snippet,
                distance=float(dist),
            )
        )
        if len(hits) >= limit:
            break

    return hits


def format_semantic_results(hits: list[SemanticSearchHit], *, query: str) -> str:
    if not hits:
        return (
            f"No semantic matches for '{query}'. "
            "Embeddings may still be missing — run catalog-embed run, "
            "or try search_games for rating-based picks."
        )
    lines = [f"Games similar in theme to '{query}':"]
    for i, h in enumerate(hits, 1):
        plat = h.platform_name or "catalog"
        blurb = h.summary or h.snippet
        if blurb and len(blurb) > 140:
            blurb = blurb[:137] + "..."
        lines.append(f"{i}. {h.name} on {plat}. {blurb}")
    return " ".join(lines)


def format_game_details(details: GameDetails) -> str:
    platforms = ", ".join(details.platforms) if details.platforms else "unknown platforms"
    genres = ", ".join(details.genres) if details.genres else "unknown genres"
    rating = (
        f"Top score about {details.best_rating:.0f}."
        if details.best_rating is not None
        else ""
    )
    summary = details.summary or details.storyline or "No description in catalog."
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return (
        f"{details.name}. Platforms: {platforms}. Genres: {genres}. {rating}"
        f"Summary: {summary}"
    )
