"""Database CLI: create extensions + tables from SQLAlchemy models."""

import argparse

from sqlalchemy import text

from catalog.database import Base, get_engine


def ensure_extensions(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()


def create_tables(engine) -> None:
    ensure_extensions(engine)
    Base.metadata.create_all(bind=engine)


def main() -> None:
    parser = argparse.ArgumentParser(description="Game catalog database utilities")
    parser.add_argument(
        "command",
        choices=["create"],
        help="create: ensure extensions and create missing tables",
    )
    parser.add_argument("--echo", action="store_true", help="Echo SQL statements")
    args = parser.parse_args()

    engine = get_engine(echo=args.echo)
    if args.command == "create":
        create_tables(engine)
        print("Database ready (extensions + tables).")


if __name__ == "__main__":
    main()
