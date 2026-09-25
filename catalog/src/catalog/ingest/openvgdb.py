"""Ingest OpenVGDB SQLite dump (no API key). https://github.com/OpenVGDB/OpenVGDB/releases"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from catalog.ingest.repository import parse_release_date, upsert_game_with_rag
from catalog.ingest.runner import ingestion_run
from catalog.ingest.util import build_rag_document, parse_genre_labels

OPENVGDB_RELEASE_URL = (
    "https://github.com/OpenVGDB/OpenVGDB/releases/latest/download/openvgdb.zip"
)

# systemShortName -> (platform slug, display name, platform_family slug)
OPENVGDB_SYSTEM_MAP: dict[str, tuple[str, str, str]] = {
    "PSX": ("ps1", "PlayStation", "playstation"),
    "PSP": ("psp", "PlayStation Portable", "playstation"),
    "NGC": ("gamecube", "Nintendo GameCube", "nintendo"),
    "N64": ("n64", "Nintendo 64", "nintendo"),
    "NDS": ("nintendo-ds", "Nintendo DS", "nintendo"),
    "SNES": ("snes", "Super Nintendo", "nintendo"),
    "NES": ("nes", "Nintendo Entertainment System", "nintendo"),
    "GBA": ("gba", "Game Boy Advance", "nintendo"),
    "GB": ("game-boy", "Game Boy", "nintendo"),
    "GBC": ("game-boy-color", "Game Boy Color", "nintendo"),
    "Wii": ("wii", "Nintendo Wii", "nintendo"),
    "Saturn": ("saturn", "Sega Saturn", "other"),
    "MD": ("mega-drive", "Sega Mega Drive", "other"),
    "SMS": ("master-system", "Sega Master System", "other"),
    "GG": ("game-gear", "Sega Game Gear", "other"),
    "PCE": ("pc-engine", "PC Engine / TurboGrafx-16", "other"),
    "2600": ("atari-2600", "Atari 2600", "other"),
}

DEFAULT_OPENVGDB_SYSTEMS = tuple(OPENVGDB_SYSTEM_MAP.keys())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def ensure_openvgdb_sqlite(cache_dir: Path | None = None) -> Path:
    cache_dir = cache_dir or (_repo_root() / ".cache" / "openvgdb")
    cache_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = cache_dir / "openvgdb.sqlite"
    if sqlite_path.exists():
        return sqlite_path
    zip_path = cache_dir / "openvgdb.zip"
    result = subprocess.run(
        ["curl", "-fsSL", OPENVGDB_RELEASE_URL, "-o", str(zip_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fallback = Path("/tmp/openvgdb.sqlite")
        if fallback.is_file():
            shutil.copy2(fallback, sqlite_path)
            return sqlite_path
        raise RuntimeError(
            f"Failed to download OpenVGDB: {result.stderr or result.stdout}"
        )
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith(".sqlite"):
                zf.extract(name, cache_dir)
                extracted = cache_dir / name
                if extracted != sqlite_path:
                    extracted.rename(sqlite_path)
                break
    if not sqlite_path.exists():
        raise FileNotFoundError("openvgdb.sqlite not found inside release zip")
    return sqlite_path


def ingest_openvgdb(
    session: Session,
    *,
    limit: int | None = 5000,
    system_short_names: tuple[str, ...] | None = None,
    cache_dir: Path | None = None,
) -> dict:
    systems = system_short_names or DEFAULT_OPENVGDB_SYSTEMS
    unknown = [s for s in systems if s not in OPENVGDB_SYSTEM_MAP]
    if unknown:
        raise ValueError(f"Unknown OpenVGDB system short names: {unknown}")

    sqlite_path = ensure_openvgdb_sqlite(cache_dir)
    placeholders = ",".join("?" for _ in systems)
    query = f"""
        SELECT releaseID, releaseTitleName, releaseDescription, releaseGenre,
               releaseDeveloper, releasePublisher, releaseDate,
               releaseReferenceURL,
               TEMPsystemShortName, TEMPsystemName
        FROM RELEASES
        WHERE TEMPsystemShortName IN ({placeholders})
        ORDER BY releaseID
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    with ingestion_run(session, "openvgdb") as stats:
        stats["sqlite_path"] = str(sqlite_path)
        stats["system_short_names"] = list(systems)
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, systems).fetchall()
        stats["rows_read"] = len(rows)

        from catalog.ingest.repository import get_or_create_platform

        for row in rows:
            short = row["TEMPsystemShortName"]
            plat_slug, plat_name, family_slug = OPENVGDB_SYSTEM_MAP[short]
            platform = get_or_create_platform(
                session,
                slug=plat_slug,
                name=plat_name,
                family_slug=family_slug,
            )
            title = (row["releaseTitleName"] or "").strip()
            if not title:
                stats["rows_skipped"] = stats.get("rows_skipped", 0) + 1
                continue

            genres = parse_genre_labels(row["releaseGenre"])
            description = (row["releaseDescription"] or "").strip()
            rag = build_rag_document(
                title=title,
                platform_name=row["TEMPsystemName"],
                summary=description,
                genres=genres,
                developer=row["releaseDeveloper"],
                publisher=row["releasePublisher"],
            )
            upsert_game_with_rag(
                session,
                source="openvgdb",
                external_id=str(row["releaseID"]),
                title=title,
                platform=platform,
                summary=description[:4000] if description else None,
                release_date=parse_release_date(row["releaseDate"]),
                store_url=row["releaseReferenceURL"],
                genre_labels=genres,
                rag_document=rag,
                chunk_metadata={
                    "source": "openvgdb",
                    "release_id": row["releaseID"],
                    "system_short_name": short,
                },
                stats=stats,
            )
        session.commit()
    return stats
