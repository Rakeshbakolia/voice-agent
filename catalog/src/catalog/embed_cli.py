"""CLI: embed game_chunk rows and report catalog maintenance stats."""

import argparse

from catalog.database import get_session_factory
from catalog.dedup import duplicate_title_report
from catalog.embeddings import (
    DEFAULT_DIMENSIONS,
    DEFAULT_MODEL,
    embed_pending_chunks,
    embedding_stats,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed game_chunk text for pgvector semantic search"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    stats_cmd = sub.add_parser("stats", help="Show embedding coverage")
    stats_cmd.add_argument(
        "--dedup",
        action="store_true",
        help="Also print top duplicate titles (same name, different game rows)",
    )
    stats_cmd.add_argument("--dedup-limit", type=int, default=15)

    run_cmd = sub.add_parser("run", help="Embed chunks with NULL embedding")
    run_cmd.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max chunks to embed this run (default: all pending)",
    )
    run_cmd.add_argument("--batch-size", type=int, default=64)
    run_cmd.add_argument("--model", type=str, default=DEFAULT_MODEL)
    run_cmd.add_argument("--dimensions", type=int, default=DEFAULT_DIMENSIONS)

    args = parser.parse_args()
    factory = get_session_factory()

    if args.command == "stats":
        with factory() as session:
            print(embedding_stats(session))
            if args.dedup:
                dupes = duplicate_title_report(session, limit=args.dedup_limit)
                print("duplicate_titles", dupes)
        return

    if args.command == "run":
        with factory() as session:
            result = embed_pending_chunks(
                session,
                limit=args.limit,
                batch_size=args.batch_size,
                model=args.model,
                dimensions=args.dimensions,
            )
        print("embed:", result)
        return


if __name__ == "__main__":
    main()
