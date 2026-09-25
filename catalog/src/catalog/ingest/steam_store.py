"""Ingest Steam Store appdetails (no API key). Rate-limit requests."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from sqlalchemy.orm import Session

from catalog.ingest.repository import get_or_create_platform
from catalog.ingest.runner import ingestion_run
from catalog.ingest.steam_common import upsert_steam_app_details

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

            if upsert_steam_app_details(
                session,
                app_id=app_id,
                data=data,
                platform=pc,
                stats=stats,
                metadata_source="steam_store",
            ):
                stats["apps_ok"] = stats.get("apps_ok", 0) + 1
            else:
                stats["apps_skipped"] = stats.get("apps_skipped", 0) + 1

        session.commit()
    return stats
