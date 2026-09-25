"""Import Steam Dataset 2025 (Zenodo) CSV/Parquet into voice-agent catalog schema.

Download: https://doi.org/10.5281/zenodo.17266922
Primary files: ``steam_games.csv`` or ``steam_games.parquet``; optional ``steam_genres.csv``.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy.orm import Session

from catalog.ingest.repository import get_or_create_platform, parse_release_date, upsert_game_with_rag
from catalog.ingest.runner import ingestion_run
from catalog.ingest.util import build_rag_document, parse_genre_labels, strip_html

SOURCE = "steam_dataset_2025"
DEFAULT_TYPES = frozenset({"game"})


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
        lower = {str(k).lower(): v for k, v in row.items()}
        for key in keys:
            lk = key.lower()
            if lk in lower and lower[lk] not in (None, ""):
                return lower[lk]
    return None


def normalize_dataset_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Zenodo CSV rows or nested Steam API JSON objects."""
    if "data" in raw and isinstance(raw["data"], dict):
        inner = dict(raw["data"])
        inner.setdefault("appid", raw.get("appid") or inner.get("steam_appid"))
        raw = inner

    appid = _pick(raw, "appid", "steam_appid", "steam_app_id", "id")
    name = _pick(raw, "name", "name_from_applist", "title")
    app_type = _pick(raw, "type", "app_type")
    if isinstance(app_type, str):
        app_type = app_type.strip().lower()

    short = _pick(raw, "short_description", "short_description_text")
    about = _pick(raw, "about_the_game", "detailed_description", "description")
    if about:
        about = strip_html(str(about))
    if short:
        short = strip_html(str(short))

    summary = (short or (about[:500] if about else None)) or None
    storyline = about if about and about != summary else None

    release = _pick(raw, "release_date", "release_date_parsed")
    mc = _pick(raw, "metacritic_score", "metacritic", "metacritic_score_materialized")
    if isinstance(mc, dict):
        mc = mc.get("score")

    genres_raw = _pick(raw, "genres", "genre", "genre_names", "tags")
    genres: list[str] = []
    if isinstance(genres_raw, str):
        genres = parse_genre_labels(genres_raw.replace(";", ","))
    elif isinstance(genres_raw, list):
        for g in genres_raw:
            if isinstance(g, dict) and g.get("description"):
                genres.append(str(g["description"]))
            elif isinstance(g, dict) and g.get("name"):
                genres.append(str(g["name"]))
            elif isinstance(g, str):
                genres.append(g)

    rating_total = None
    if mc is not None:
        try:
            rating_total = float(mc)
        except (TypeError, ValueError):
            rating_total = None

    return {
        "appid": int(appid) if appid is not None else None,
        "name": str(name).strip() if name else None,
        "type": app_type,
        "summary": summary,
        "storyline": storyline,
        "release_date": parse_release_date(str(release)) if release else None,
        "rating_total": rating_total,
        "metacritic_score": int(rating_total) if rating_total is not None else None,
        "genres": genres,
    }


def _load_zenodo_genre_join(
    application_genres_path: Path, genres_path: Path
) -> dict[int, list[str]]:
    id_to_name: dict[int, str] = {}
    with genres_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            gid = _pick(row, "id", "genre_id")
            name = _pick(row, "name", "genre_name")
            if gid is None or not name:
                continue
            id_to_name[int(gid)] = str(name).strip()

    mapping: dict[int, list[str]] = {}
    with application_genres_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            appid = _pick(row, "appid", "steam_appid", "application_id")
            genre_id = _pick(row, "genre_id", "genre")
            if appid is None or genre_id is None:
                continue
            label = id_to_name.get(int(genre_id))
            if not label:
                continue
            aid = int(appid)
            mapping.setdefault(aid, [])
            if label not in mapping[aid]:
                mapping[aid].append(label)
    return mapping


def load_genres_map(
    path: Path, genre_names_path: Path | None = None
) -> dict[int, list[str]]:
    """Zenodo ``application_genres.csv`` + ``genres.csv``, or flat appid+genre CSV."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])

    if "genre_id" in fields:
        names_path = genre_names_path or path.parent / "genres.csv"
        if not names_path.is_file():
            raise FileNotFoundError(
                f"Genre join file needs genres.csv beside it or --genre-names-file; missing {names_path}"
            )
        return _load_zenodo_genre_join(path, names_path)

    mapping: dict[int, list[str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            appid = _pick(row, "appid", "steam_appid", "application_id")
            genre = _pick(row, "genre", "genre_name", "name", "description")
            if appid is None or not genre:
                continue
            aid = int(appid)
            label = str(genre).strip()
            if label:
                mapping.setdefault(aid, [])
                if label not in mapping[aid]:
                    mapping[aid].append(label)
    return mapping


def iter_dataset_rows(path: Path) -> Iterator[dict[str, Any]]:
    suffix = path.suffix.lower()
    name = path.name.lower()

    if suffix == ".gz":
        if name.endswith(".json.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(payload, dict):
                for value in payload.values():
                    if isinstance(value, dict):
                        yield value
            return
        raise ValueError(f"Unsupported gzip file: {path}")

    if suffix == ".json":
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    yield item
        elif isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, dict):
                    yield value
        return

    if suffix == ".parquet":
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=256):
            for row in batch.to_pylist():
                yield row
        return

    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield row
        return

    raise ValueError(f"Unsupported file type: {path} (use .csv, .parquet, .json, or .json.gz)")


def ingest_steam_dataset(
    session: Session,
    *,
    games_file: Path,
    genres_file: Path | None = None,
    genre_names_file: Path | None = None,
    limit: int | None = None,
    allowed_types: frozenset[str] | None = None,
    include_non_games: bool = False,
) -> dict:
    if not games_file.is_file():
        raise FileNotFoundError(f"Games file not found: {games_file}")

    allowed = None if include_non_games else (allowed_types or DEFAULT_TYPES)
    genres_map = (
        load_genres_map(genres_file, genre_names_file) if genres_file else {}
    )

    pc = get_or_create_platform(
        session,
        slug="pc-windows",
        name="PC (Windows)",
        family_slug="pc",
    )

    with ingestion_run(session, SOURCE) as stats:
        stats["games_file"] = str(games_file)
        stats["genres_file"] = str(genres_file) if genres_file else None

        for index, raw_row in enumerate(iter_dataset_rows(games_file)):
            if limit is not None and index >= limit:
                break

            stats["rows_read"] = stats.get("rows_read", 0) + 1
            row = normalize_dataset_row(raw_row)

            if row["appid"] is None or not row["name"]:
                stats["rows_skipped"] = stats.get("rows_skipped", 0) + 1
                continue

            if allowed is not None:
                row_type = row.get("type") or "game"
                if row_type not in allowed:
                    stats["rows_skipped_type"] = stats.get("rows_skipped_type", 0) + 1
                    continue

            appid = row["appid"]
            genres = list(row["genres"]) if row["genres"] else []
            for g in genres_map.get(appid, []):
                if g not in genres:
                    genres.append(g)

            store_url = f"https://store.steampowered.com/app/{appid}/"
            rag = build_rag_document(
                title=row["name"],
                platform_name="PC (Steam)",
                summary=row["summary"],
                genres=genres,
                extra=f"Steam appid: {appid}; source: {SOURCE}",
            )
            if row["storyline"]:
                rag = f"{rag}\nDescription: {row['storyline'][:6000]}"

            upsert_game_with_rag(
                session,
                source="steam",
                external_id=str(appid),
                title=row["name"],
                platform=pc,
                summary=row["summary"],
                storyline=row["storyline"],
                release_date=row["release_date"],
                store_url=store_url,
                genre_labels=genres,
                rating_critic=row["rating_total"],
                rating_total=row["rating_total"],
                metacritic_score=row["metacritic_score"],
                rag_document=rag,
                chunk_metadata={
                    "source": SOURCE,
                    "steam_appid": appid,
                    "dataset_file": games_file.name,
                },
                stats=stats,
            )

            if stats["rows_read"] % 500 == 0:
                session.commit()

        session.commit()

    return stats
