from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from sqlalchemy.orm import Session

from catalog.models import IngestionRun


@contextmanager
def ingestion_run(
    session: Session, source: str
) -> Generator[dict[str, Any], None, None]:
    run = IngestionRun(source=source, status="running", stats={})
    session.add(run)
    session.commit()
    stats: dict[str, Any] = {}
    try:
        yield stats
        run.status = "success"
        run.stats = stats
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
    except Exception as exc:
        session.rollback()
        run = session.get(IngestionRun, run.id)
        if run:
            run.status = "failed"
            run.error_message = str(exc)[:2000]
            run.stats = stats
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
        raise
