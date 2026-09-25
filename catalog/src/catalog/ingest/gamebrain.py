"""Ingest from GameBrain API. https://gamebrain.co/api/docs/quickstart"""

from __future__ import annotations

import json
import os
import subprocess
import time
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from catalog.ingest.repository import get_or_create_platform, parse_release_date, upsert_game_with_rag
from catalog.ingest.runner import ingestion_run
from catalog.ingest.util import build_rag_document

GAMEBRAIN_API_BASE = "https://api.gamebrain.co/v1"

# GameBrain platform filter -> (our platform slug, display name, family slug)
DEFAULT_GAMEBRAIN_PLATFORMS: dict[str, tuple[str, str, str]] = {
    "playstation_5": ("ps5", "PlayStation 5", "playstation"),
    "playstation_4": ("ps4", "PlayStation 4", "playstation"),
    "playstation_3": ("ps3", "PlayStation 3", "playstation"),
    "xbox_series_x": ("xbox-series-x", "Xbox Series X|S", "xbox"),
    "xbox_one": ("xbox-one", "Xbox One", "xbox"),
    "nintendo_switch": ("nintendo-switch", "Nintendo Switch", "nintendo"),
    "pc": ("pc-windows", "PC (Windows)", "pc"),
}


def get_gamebrain_api_key() -> str:
    key = os.getenv("GAMEBRAIN_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GAMEBRAIN_API_KEY in .env.local")
    return key


def gamebrain_request(
    api_key: str,
    path: str,
    params: dict | None = None,
) -> dict | list:
    params = dict(params or {})
    query = urlencode(params)
    url = f"{GAMEBRAIN_API_BASE}{path}"
    if query:
        url = f"{url}?{query}"

    result = subprocess.run(
        [
            "curl",
            "-fsSL",
            "-H",
            f"Authorization: Bearer {api_key}",
            "-H",
            "Accept: application/json",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"GameBrain request failed ({path}): {result.stderr or result.stdout}"
        )
    return json.loads(result.stdout)


def _genre_labels(game: dict) -> list[str]:
    labels: list[str] = []
    if game.get("genre"):
        labels.append(str(game["genre"]))
    for g in game.get("genres") or []:
        if isinstance(g, dict) and g.get("name"):
            labels.append(str(g["name"]))
        elif isinstance(g, str):
            labels.append(g)
    return labels


def _rating_total(game: dict) -> float | None:
    rating = game.get("rating")
    if isinstance(rating, dict) and rating.get("mean") is not None:
        # GameBrain mean is typically 0–10; normalize to 0–100
        return float(rating["mean"]) * 10.0
    if game.get("score") is not None:
        return float(game["score"])
    return None


def _pick_platform_for_game(
    game: dict, gb_platform_key: str
) -> tuple[str, str, str]:
    """Prefer GameBrain platform list when present."""
    platforms = game.get("platforms") or []
    for p in platforms:
        if isinstance(p, dict):
            slug = (p.get("slug") or p.get("id") or "").lower()
            if slug and slug in DEFAULT_GAMEBRAIN_PLATFORMS:
                return DEFAULT_GAMEBRAIN_PLATFORMS[slug]
    return DEFAULT_GAMEBRAIN_PLATFORMS[gb_platform_key]


def ingest_gamebrain(
    session: Session,
    *,
    platforms: tuple[str, ...] | None = None,
    limit_per_platform: int = 50,
    sort: str = "rating",
    delay_seconds: float = 0.5,
) -> dict:
    api_key = get_gamebrain_api_key()
    platform_keys = platforms or tuple(DEFAULT_GAMEBRAIN_PLATFORMS.keys())
    unknown = [p for p in platform_keys if p not in DEFAULT_GAMEBRAIN_PLATFORMS]
    if unknown:
        raise ValueError(f"Unknown GameBrain platform keys: {unknown}")

    with ingestion_run(session, "gamebrain") as stats:
        stats["platforms"] = list(platform_keys)
        stats["limit_per_platform"] = limit_per_platform

        for gb_key in platform_keys:
            if delay_seconds > 0:
                time.sleep(delay_seconds)

            payload = gamebrain_request(
                api_key,
                "/games",
                {
                    "platform": gb_key,
                    "sort": sort,
                    "limit": str(limit_per_platform),
                    "query": "games",
                },
            )
            games = payload if isinstance(payload, list) else payload.get("games") or payload.get("results") or []
            if isinstance(games, dict):
                games = games.get("items") or []

            imported = 0
            for game in games:
                if not isinstance(game, dict):
                    continue
                game_id = game.get("id")
                title = (game.get("name") or "").strip()
                if game_id is None or not title:
                    continue

                plat_slug, plat_name, family_slug = _pick_platform_for_game(game, gb_key)
                platform = get_or_create_platform(
                    session,
                    slug=plat_slug,
                    name=plat_name,
                    family_slug=family_slug,
                )

                summary = (game.get("short_description") or game.get("description") or "")
                if summary:
                    summary = str(summary).strip()[:4000]
                else:
                    summary = None

                genres = _genre_labels(game)
                rating = _rating_total(game)
                developer = game.get("developer")
                if isinstance(developer, dict):
                    developer = developer.get("name")
                developer = str(developer) if developer else None

                release_raw = game.get("release_date") or game.get("year")
                if release_raw is not None and not isinstance(release_raw, str):
                    release_raw = str(release_raw)

                extra_parts = []
                if isinstance(game.get("rating"), dict) and game["rating"].get("count"):
                    extra_parts.append(f"GameBrain reviews: {game['rating']['count']}")
                if game.get("url"):
                    extra_parts.append(f"URL: {game['url']}")

                rag = build_rag_document(
                    title=title,
                    platform_name=plat_name,
                    summary=summary,
                    genres=genres,
                    developer=developer,
                    extra="\n".join(extra_parts) if extra_parts else None,
                )

                upsert_game_with_rag(
                    session,
                    source="gamebrain",
                    external_id=str(game_id),
                    title=title,
                    platform=platform,
                    summary=summary,
                    release_date=parse_release_date(release_raw),
                    store_url=str(game["url"]) if game.get("url") else None,
                    genre_labels=genres,
                    rating_total=rating,
                    rating_user=rating,
                    rag_document=rag,
                    chunk_metadata={
                        "source": "gamebrain",
                        "gamebrain_id": game_id,
                        "gamebrain_platform_filter": gb_key,
                    },
                    stats=stats,
                )
                imported += 1

            stats.setdefault("games_by_platform", {})[gb_key] = imported
            session.commit()

    return stats
