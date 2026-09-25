"""Ingest Steam Store appdetails (no API key). Rate-limit requests."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from sqlalchemy.orm import Session

from catalog.ingest.repository import get_or_create_platform, parse_release_date, upsert_game_with_rag
from catalog.ingest.runner import ingestion_run
from catalog.ingest.util import build_rag_document, strip_html

STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
DEFAULT_APPIDS_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "steam_seed_appids.txt"
)


def load_app_ids(path: Path | None = None) -> list[int]:
    path = path or DEFAULT_APPIDS_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Steam app id list not found: {path}")
    ids: list[int] = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.append(int(line))
    return ids


def fetch_app_details(app_id: int, *, language: str = "english") -> dict | None:
    url = f"{STEAM_APPDETAILS_URL}?appids={app_id}&l={language}"
    try:
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "-A",
                "voice-agent-catalog/0.1",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return None
    if not payload:
        return None
    entry = payload.get(str(app_id))
    if entry is None:
        entry = next(iter(payload.values()))
    if not entry or not entry.get("success"):
        return None
    return entry.get("data") or None


def ingest_steam_store(
    session: Session,
    *,
    app_ids: list[int] | None = None,
    appids_file: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 1.25,
) -> dict:
    ids = app_ids or load_app_ids(appids_file)
    if limit is not None:
        ids = ids[: int(limit)]

    pc = get_or_create_platform(
        session,
        slug="pc-windows",
        name="PC (Windows)",
        family_slug="pc",
    )

    with ingestion_run(session, "steam_store") as stats:
        stats["app_ids_requested"] = len(ids)
        stats["delay_seconds"] = delay_seconds

        for index, app_id in enumerate(ids):
            if index > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)

            data = fetch_app_details(app_id)
            if not data:
                stats["apps_failed"] = stats.get("apps_failed", 0) + 1
                continue

            if data.get("type") not in (None, "game", "dlc"):
                stats["apps_skipped"] = stats.get("apps_skipped", 0) + 1
                continue

            title = (data.get("name") or "").strip()
            if not title:
                stats["apps_skipped"] = stats.get("apps_skipped", 0) + 1
                continue

            short = strip_html(data.get("short_description"))
            about = strip_html(data.get("about_the_game") or data.get("detailed_description"))
            summary = short or about[:500]
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
                platform=pc,
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
                    "source": "steam_store",
                    "steam_appid": app_id,
                },
                stats=stats,
            )
            stats["apps_ok"] = stats.get("apps_ok", 0) + 1

        session.commit()
    return stats
