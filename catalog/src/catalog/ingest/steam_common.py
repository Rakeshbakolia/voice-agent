"""Shared Steam store upsert logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from catalog.ingest.repository import parse_release_date, upsert_game_with_rag
from catalog.ingest.util import build_rag_document, strip_html
from catalog.models import Platform


def upsert_steam_app_details(
    session: Session,
    *,
    app_id: int,
    data: dict,
    platform: Platform,
    stats: dict,
    metadata_source: str = "steam_store",
) -> bool:
    if data.get("type") not in (None, "game", "dlc"):
        return False

    title = (data.get("name") or "").strip()
    if not title:
        return False

    short = strip_html(data.get("short_description"))
    about = strip_html(data.get("about_the_game") or data.get("detailed_description"))
    summary = short or (about[:500] if about else None)
    storyline = about if about and about != summary else None

    genres = [g.get("description", "") for g in data.get("genres", []) if g.get("description")]
    developers = ", ".join(data.get("developers") or [])
    publishers = ", ".join(data.get("publishers") or [])

    metacritic = data.get("metacritic") or {}
    mc_score = metacritic.get("score")
    rating_total = float(mc_score) if mc_score is not None else None

    release = data.get("release_date") or {}
    release_raw = release.get("date") if not release.get("coming_soon") else None

    store_url = f"https://store.steampowered.com/app/{app_id}/"
    extra = None
    rec = data.get("recommendations") or {}
    if rec.get("total"):
        extra = f"Steam recommendations: {rec['total']}"

    rag = build_rag_document(
        title=title,
        platform_name="PC (Steam)",
        summary=summary,
        genres=genres,
        developer=developers or None,
        publisher=publishers or None,
        extra=extra,
    )
    if storyline and storyline not in rag:
        rag = f"{rag}\nLong description: {storyline[:6000]}"

    upsert_game_with_rag(
        session,
        source="steam",
        external_id=str(app_id),
        title=title,
        platform=platform,
        summary=summary,
        storyline=storyline[:8000] if storyline else None,
        release_date=parse_release_date(release_raw),
        store_url=store_url,
        genre_labels=genres,
        rating_critic=rating_total,
        rating_total=rating_total,
        metacritic_score=int(mc_score) if mc_score is not None else None,
        rag_document=rag,
        chunk_metadata={
            "source": metadata_source,
            "steam_appid": app_id,
        },
        stats=stats,
    )
    return True
