#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/rakeshbakolia/work/system design/voice-agent"
CSV="/Users/rakeshbakolia/Downloads/steam_dataset_2025_csv"
export PATH="${HOME}/.local/bin:${PATH}"

cd "$ROOT"
docker compose up -d

cd "$ROOT/catalog"
uv sync

run() {
  echo ""
  echo "========== $(date -Iseconds) $* =========="
  uv run catalog-ingest "$@"
}

run openvgdb --limit 80000
run steam-store --delay 1.0
run igdb --games-per-platform 100 --delay 0.26
run rawg --games-per-platform 100 --delay 0.35
run gamebrain --limit-per-platform 50 --delay 0.5
run steam-api --list-limit 5000 --enrich-limit 800 --delay 1.0
run steam-dataset \
  --file "$CSV/applications.csv" \
  --genres-file "$CSV/application_genres.csv" \
  --genre-names-file "$CSV/genres.csv"

echo ""
echo "========== $(date -Iseconds) DONE — counts =========="
uv run python -c "
from sqlalchemy import func, select
from catalog import Game, GameChunk, IngestionRun
from catalog.database import get_session_factory
with get_session_factory()() as s:
    print('games', s.scalar(select(func.count()).select_from(Game)))
    print('chunks', s.scalar(select(func.count()).select_from(GameChunk)))
    for r in s.scalars(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(12)):
        print(r.source, r.status, r.stats)
"
