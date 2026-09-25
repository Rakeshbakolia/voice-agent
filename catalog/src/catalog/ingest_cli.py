"""CLI for catalog ingestion jobs."""

import argparse
from pathlib import Path

from catalog.database import get_session_factory
from catalog.ingest.gamebrain import DEFAULT_GAMEBRAIN_PLATFORMS, ingest_gamebrain
from catalog.ingest.igdb import DEFAULT_IGDB_PLATFORM_IDS, ingest_igdb
from catalog.ingest.rawg import DEFAULT_RAWG_PLATFORM_IDS, ingest_rawg
from catalog.ingest.openvgdb import DEFAULT_OPENVGDB_SYSTEMS, ingest_openvgdb
from catalog.ingest.steam_api import ingest_steam_api
from catalog.ingest.steam_dataset import ingest_steam_dataset
from catalog.ingest.steam_store import ingest_steam_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest game data into Postgres + RAG chunks")
    sub = parser.add_subparsers(dest="command", required=True)

    openvgdb = sub.add_parser("openvgdb", help="OpenVGDB SQLite dump (no API key)")
    openvgdb.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Max release rows to import (default 5000)",
    )
    openvgdb.add_argument(
        "--systems",
        type=str,
        default=",".join(DEFAULT_OPENVGDB_SYSTEMS),
        help="Comma-separated OpenVGDB TEMPsystemShortName values",
    )
    openvgdb.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Directory for downloaded openvgdb.sqlite",
    )

    steam = sub.add_parser("steam-store", help="Steam Store appdetails (no API key)")
    steam.add_argument(
        "--appids-file",
        type=Path,
        default=None,
        help="Text file with one Steam app id per line",
    )
    steam.add_argument("--limit", type=int, default=None, help="Max app ids to fetch")
    steam.add_argument(
        "--delay",
        type=float,
        default=1.25,
        help="Seconds between Steam HTTP requests",
    )

    all_cmd = sub.add_parser(
        "no-auth",
        help="Run all no-auth ingests (OpenVGDB + Steam store)",
    )
    all_cmd.add_argument("--openvgdb-limit", type=int, default=3000)
    all_cmd.add_argument("--steam-limit", type=int, default=25)
    all_cmd.add_argument("--delay", type=float, default=1.25)

    igdb = sub.add_parser("igdb", help="IGDB via Twitch OAuth (TWITCH_CLIENT_ID/SECRET)")
    igdb.add_argument(
        "--platform-ids",
        type=str,
        default=",".join(str(i) for i in DEFAULT_IGDB_PLATFORM_IDS),
        help="Comma-separated IGDB platform ids",
    )
    igdb.add_argument(
        "--games-per-platform",
        type=int,
        default=100,
        help="Top-rated games to import per platform (default 100)",
    )
    igdb.add_argument("--page-size", type=int, default=50, help="IGDB page size (max 500)")
    igdb.add_argument(
        "--delay",
        type=float,
        default=0.26,
        help="Seconds between IGDB HTTP requests (~4/sec limit)",
    )
    igdb.add_argument(
        "--skip-genres",
        action="store_true",
        help="Do not refresh genre table from IGDB",
    )

    steam_api = sub.add_parser(
        "steam-api",
        help="Steam Web API app list + store enrich (STEAM_WEB_API_KEY)",
    )
    steam_api.add_argument(
        "--list-limit",
        type=int,
        default=500,
        help="Max app IDs to fetch from GetAppList",
    )
    steam_api.add_argument(
        "--enrich-limit",
        type=int,
        default=None,
        help="Max apps to enrich via appdetails (default: same as list-limit)",
    )
    steam_api.add_argument("--page-size", type=int, default=500)
    steam_api.add_argument("--delay", type=float, default=1.25)

    gamebrain = sub.add_parser(
        "gamebrain",
        help="GameBrain catalog (GAMEBRAIN_API_KEY)",
    )
    gamebrain.add_argument(
        "--platforms",
        type=str,
        default=",".join(DEFAULT_GAMEBRAIN_PLATFORMS.keys()),
        help="Comma-separated GameBrain platform filters",
    )
    gamebrain.add_argument("--limit-per-platform", type=int, default=50)
    gamebrain.add_argument(
        "--sort",
        type=str,
        default="rating",
        help="GameBrain sort parameter (e.g. rating)",
    )
    gamebrain.add_argument("--delay", type=float, default=0.5)

    steam_ds = sub.add_parser(
        "steam-dataset",
        help="Steam Dataset 2025 CSV/Parquet (Zenodo) offline import",
    )
    steam_ds.add_argument(
        "--file",
        type=Path,
        required=True,
        help="applications.csv / steam_games.csv, .parquet, .json, or .json.gz",
    )
    steam_ds.add_argument(
        "--genres-file",
        type=Path,
        default=None,
        help="Optional genres: steam_genres.csv or Zenodo application_genres.csv",
    )
    steam_ds.add_argument(
        "--genre-names-file",
        type=Path,
        default=None,
        help="Zenodo genres.csv when using application_genres.csv",
    )
    steam_ds.add_argument("--limit", type=int, default=None, help="Max rows to import")
    steam_ds.add_argument(
        "--include-non-games",
        action="store_true",
        help="Import DLC/software/etc., not only type=game",
    )

    rawg = sub.add_parser("rawg", help="RAWG.io catalog (RAWG_API_KEY)")
    rawg.add_argument(
        "--platform-ids",
        type=str,
        default=",".join(str(i) for i in DEFAULT_RAWG_PLATFORM_IDS),
        help="Comma-separated RAWG platform ids",
    )
    rawg.add_argument("--games-per-platform", type=int, default=100)
    rawg.add_argument("--page-size", type=int, default=40)
    rawg.add_argument("--delay", type=float, default=0.35)
    rawg.add_argument("--skip-genres", action="store_true")

    phase2 = sub.add_parser(
        "phase2",
        help="Run Steam Web API + GameBrain ingests",
    )
    phase2.add_argument("--steam-list-limit", type=int, default=200)
    phase2.add_argument("--steam-enrich-limit", type=int, default=50)
    phase2.add_argument("--steam-delay", type=float, default=1.25)
    phase2.add_argument("--gamebrain-limit", type=int, default=30)
    phase2.add_argument("--gamebrain-delay", type=float, default=0.5)

    args = parser.parse_args()
    Session = get_session_factory()

    with Session() as session:
        if args.command == "openvgdb":
            systems = tuple(s.strip() for s in args.systems.split(",") if s.strip())
            stats = ingest_openvgdb(
                session,
                limit=args.limit,
                system_short_names=systems,
                cache_dir=args.cache_dir,
            )
            print("openvgdb:", stats)
        elif args.command == "steam-store":
            stats = ingest_steam_store(
                session,
                appids_file=args.appids_file,
                limit=args.limit,
                delay_seconds=args.delay,
            )
            print("steam-store:", stats)
        elif args.command == "no-auth":
            ostats = ingest_openvgdb(session, limit=args.openvgdb_limit)
            print("openvgdb:", ostats)
            sstats = ingest_steam_store(
                session,
                limit=args.steam_limit,
                delay_seconds=args.delay,
            )
            print("steam-store:", sstats)
        elif args.command == "igdb":
            platform_ids = tuple(
                int(x.strip()) for x in args.platform_ids.split(",") if x.strip()
            )
            stats = ingest_igdb(
                session,
                platform_ids=platform_ids,
                games_per_platform=args.games_per_platform,
                page_size=args.page_size,
                delay_seconds=args.delay,
                sync_genres=not args.skip_genres,
            )
            print("igdb:", stats)
        elif args.command == "steam-api":
            stats = ingest_steam_api(
                session,
                list_limit=args.list_limit,
                enrich_limit=args.enrich_limit,
                page_size=args.page_size,
                delay_seconds=args.delay,
            )
            print("steam-api:", stats)
        elif args.command == "gamebrain":
            platforms = tuple(
                p.strip() for p in args.platforms.split(",") if p.strip()
            )
            stats = ingest_gamebrain(
                session,
                platforms=platforms,
                limit_per_platform=args.limit_per_platform,
                sort=args.sort,
                delay_seconds=args.delay,
            )
            print("gamebrain:", stats)
        elif args.command == "rawg":
            platform_ids = tuple(
                int(x.strip()) for x in args.platform_ids.split(",") if x.strip()
            )
            stats = ingest_rawg(
                session,
                platform_ids=platform_ids,
                games_per_platform=args.games_per_platform,
                page_size=args.page_size,
                delay_seconds=args.delay,
                sync_genres=not args.skip_genres,
            )
            print("rawg:", stats)
        elif args.command == "steam-dataset":
            stats = ingest_steam_dataset(
                session,
                games_file=args.file,
                genres_file=args.genres_file,
                genre_names_file=args.genre_names_file,
                limit=args.limit,
                include_non_games=args.include_non_games,
            )
            print("steam-dataset:", stats)
        elif args.command == "phase2":
            sstats = ingest_steam_api(
                session,
                list_limit=args.steam_list_limit,
                enrich_limit=args.steam_enrich_limit,
                delay_seconds=args.steam_delay,
            )
            print("steam-api:", sstats)
            gstats = ingest_gamebrain(
                session,
                limit_per_platform=args.gamebrain_limit,
                delay_seconds=args.gamebrain_delay,
            )
            print("gamebrain:", gstats)


if __name__ == "__main__":
    main()
