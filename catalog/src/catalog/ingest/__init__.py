"""Batch ingest from external game data sources into Postgres + game_chunk (RAG text)."""

from catalog.ingest.gamebrain import ingest_gamebrain
from catalog.ingest.igdb import ingest_igdb
from catalog.ingest.rawg import ingest_rawg
from catalog.ingest.openvgdb import ingest_openvgdb
from catalog.ingest.steam_api import ingest_steam_api
from catalog.ingest.steam_dataset import ingest_steam_dataset
from catalog.ingest.steam_store import ingest_steam_store

__all__ = [
    "ingest_gamebrain",
    "ingest_igdb",
    "ingest_rawg",
    "ingest_openvgdb",
    "ingest_steam_api",
    "ingest_steam_dataset",
    "ingest_steam_store",
]
