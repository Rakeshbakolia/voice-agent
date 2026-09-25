"""CLI for catalog ingestion jobs."""

import argparse
from pathlib import Path

from catalog.database import get_session_factory
from catalog.ingest.igdb import DEFAULT_IGDB_PLATFORM_IDS, ingest_igdb
from catalog.ingest.openvgdb import DEFAULT_OPENVGDB_SYSTEMS, ingest_openvgdb
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


if __name__ == "__main__":
    main()
