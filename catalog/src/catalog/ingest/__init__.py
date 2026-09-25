"""Batch ingest from external game data sources into Postgres + game_chunk (RAG text)."""

from catalog.ingest.igdb import ingest_igdb
from catalog.ingest.openvgdb import ingest_openvgdb
from catalog.ingest.steam_store import ingest_steam_store

__all__ = ["ingest_igdb", "ingest_openvgdb", "ingest_steam_store"]
