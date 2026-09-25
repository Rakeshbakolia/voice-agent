"""Report duplicate game titles across ingest sources (merge not automated yet)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from catalog.models import Game


def duplicate_title_report(session: Session, *, limit: int = 25) -> list[tuple[str, int]]:
    """Return (lowercase title, count) for titles that appear more than once."""
    limit = max(1, min(limit, 100))
    rows = session.execute(
        select(func.lower(Game.name), func.count())
        .group_by(func.lower(Game.name))
        .having(func.count() > 1)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return [(str(name), int(count)) for name, count in rows]
