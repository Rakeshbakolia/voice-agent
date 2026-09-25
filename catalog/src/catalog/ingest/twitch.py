"""Twitch OAuth (client credentials) for IGDB API."""

from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


def get_twitch_client_credentials() -> tuple[str, str]:
    client_id = os.getenv("TWITCH_CLIENT_ID", "").strip()
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET in .env.local"
        )
    return client_id, client_secret


@lru_cache(maxsize=1)
def get_app_access_token() -> tuple[str, str]:
    """Return (access_token, client_id). Cached for process lifetime."""
    client_id, client_secret = get_twitch_client_credentials()
    url = (
        f"{TWITCH_TOKEN_URL}?client_id={client_id}"
        f"&client_secret={client_secret}&grant_type=client_credentials"
    )
    result = subprocess.run(
        ["curl", "-fsSL", "-X", "POST", url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Twitch OAuth failed: {result.stderr or result.stdout or 'unknown error'}"
        )
    payload = json.loads(result.stdout)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"Twitch OAuth response missing access_token: {payload}")
    return token, client_id
