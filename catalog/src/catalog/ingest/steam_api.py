"""Discover Steam app IDs via Web API, enrich with store appdetails."""

from __future__ import annotations

import json
import os
import subprocess
import time
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from catalog.ingest.repository import get_or_create_platform
from catalog.ingest.runner import ingestion_run
from catalog.ingest.steam_common import upsert_steam_app_details
from catalog.ingest.steam_store import fetch_app_details

STEAM_GET_APP_LIST = "https://api.steampowered.com/IStoreService/GetAppList/v1/"


def get_steam_web_api_key() -> str:
    key = os.getenv("STEAM_WEB_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing STEAM_WEB_API_KEY in .env.local")
    return key


def fetch_app_list_page(
    api_key: str,
    *,
    last_appid: int = 0,
    max_results: int = 500,
) -> dict:
    params = urlencode(
        {
            "key": api_key,
            "last_appid": last_appid,
            "max_results": max_results,
        }
    )
    url = f"{STEAM_GET_APP_LIST}?{params}"
    result = subprocess.run(
        ["curl", "-fsSL", url],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Steam GetAppList failed: {result.stderr or result.stdout}"
        )
    payload = json.loads(result.stdout)
    return payload.get("response") or {}


def collect_app_ids(
    api_key: str,
    *,
    max_apps: int,
    page_size: int = 500,
) -> list[int]:
    ids: list[int] = []
    last_appid = 0
    while len(ids) < max_apps:
        page = fetch_app_list_page(
            api_key, last_appid=last_appid, max_results=min(page_size, max_apps - len(ids))
        )
        apps = page.get("apps") or []
        if not apps:
            break
        for app in apps:
            appid = app.get("appid")
            if appid is not None:
                ids.append(int(appid))
                if len(ids) >= max_apps:
                    break
        if not page.get("have_more"):
            break
        last_appid = int(page.get("last_appid") or apps[-1].get("appid", last_appid))
        if last_appid == 0:
            break
    return ids


def ingest_steam_api(
    session: Session,
    *,
    list_limit: int = 500,
    enrich_limit: int | None = None,
    page_size: int = 500,
    delay_seconds: float = 1.25,
) -> dict:
    """Fetch app IDs from IStoreService/GetAppList, then store metadata via appdetails."""
    api_key = get_steam_web_api_key()
    enrich_limit = enrich_limit if enrich_limit is not None else list_limit

    pc = get_or_create_platform(
        session,
        slug="pc-windows",
        name="PC (Windows)",
        family_slug="pc",
    )

    with ingestion_run(session, "steam_api") as stats:
        app_ids = collect_app_ids(api_key, max_apps=list_limit, page_size=page_size)
        stats["app_ids_discovered"] = len(app_ids)
        stats["enrich_limit"] = enrich_limit
        stats["delay_seconds"] = delay_seconds

        to_enrich = app_ids[:enrich_limit]
        for index, app_id in enumerate(to_enrich):
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
                metadata_source="steam_api",
            ):
                stats["apps_ok"] = stats.get("apps_ok", 0) + 1
            else:
                stats["apps_skipped"] = stats.get("apps_skipped", 0) + 1

        session.commit()

    return stats
