"""Embed ``game_chunk`` rows for pgvector semantic search (1536-dim)."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

import certifi
from typing import Any, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from catalog.ingest.runner import ingestion_run
from catalog.models import Game, GameChunk, Platform

SOURCE = "chunk_embeddings"
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
MAX_CHARS_PER_CHUNK = 8000


def get_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for embeddings. "
            "Set it in .env.local (model: text-embedding-3-small, 1536 dimensions)."
        )
    return key


def truncate_for_embed(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


def embed_texts_openai(
    texts: Sequence[str],
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
) -> list[list[float]]:
    if not texts:
        return []
    payload = {
        "model": model,
        "input": list(texts),
        "dimensions": dimensions,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, timeout=120, context=ssl_ctx) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI embeddings HTTP {exc.code}: {detail[:500]}") from exc

    data = body.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected OpenAI embeddings response: {body!r}")
    ordered = sorted(data, key=lambda row: row.get("index", 0))
    vectors: list[list[float]] = []
    for row in ordered:
        embedding = row.get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError(f"Missing embedding in row: {row!r}")
        if len(embedding) != dimensions:
            raise RuntimeError(
                f"Expected {dimensions} dimensions, got {len(embedding)} for model {model}"
            )
        vectors.append([float(x) for x in embedding])
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"OpenAI returned {len(vectors)} vectors for {len(texts)} inputs"
        )
    return vectors


def embedding_stats(session: Session) -> dict[str, int]:
    total = session.scalar(select(func.count()).select_from(GameChunk)) or 0
    missing = (
        session.scalar(
            select(func.count()).select_from(GameChunk).where(GameChunk.embedding.is_(None))
        )
        or 0
    )
    return {
        "chunks_total": int(total),
        "chunks_without_embedding": int(missing),
        "chunks_with_embedding": int(total) - int(missing),
    }


def embed_pending_chunks(
    session: Session,
    *,
    limit: Optional[int] = None,
    batch_size: int = 64,
    model: str = DEFAULT_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Fill ``NULL`` embeddings in batches. Returns stats dict."""
    batch_size = max(1, min(batch_size, 256))
    key = api_key or get_openai_api_key()

    with ingestion_run(session, SOURCE) as stats:
        stats["model"] = model
        stats["dimensions"] = dimensions
        stats["batch_size"] = batch_size
        stats.update(embedding_stats(session))

        embedded = 0
        batches = 0
        while True:
            if limit is not None and embedded >= limit:
                break
            fetch = batch_size
            if limit is not None:
                fetch = min(fetch, limit - embedded)

            chunks = session.scalars(
                select(GameChunk)
                .where(GameChunk.embedding.is_(None))
                .order_by(GameChunk.created_at)
                .limit(fetch)
            ).all()
            if not chunks:
                break

            texts = [truncate_for_embed(c.content) for c in chunks]
            vectors = embed_texts_openai(
                texts, api_key=key, model=model, dimensions=dimensions
            )
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = vector
            session.commit()
            embedded += len(chunks)
            batches += 1
            stats["chunks_embedded"] = embedded
            stats["batches"] = batches

        stats.update(embedding_stats(session))

    return stats


def embed_query_text(
    query: str,
    *,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
) -> list[float]:
    key = api_key or get_openai_api_key()
    vectors = embed_texts_openai(
        [truncate_for_embed(query)],
        api_key=key,
        model=model,
        dimensions=dimensions,
    )
    return vectors[0]
