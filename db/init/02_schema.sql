-- Multi-platform game catalog + optional semantic chunks (RAG / descriptions).
-- Embedding dimension must match your embedding model (default 1536, e.g. OpenAI text-embedding-3-small).

-- ---------------------------------------------------------------------------
-- Reference: platform families (PlayStation, Xbox, PC, Nintendo, …)
-- ---------------------------------------------------------------------------
CREATE TABLE platform_family (
    id          SMALLSERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Platforms / versions (PS2, PS5, Xbox Series X|S, PC Windows, Steam as store, …)
-- ---------------------------------------------------------------------------
CREATE TABLE platform (
    id              SMALLSERIAL PRIMARY KEY,
    family_id       SMALLINT REFERENCES platform_family (id) ON DELETE SET NULL,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    generation      SMALLINT,
    igdb_id         INTEGER UNIQUE,
    rawg_id         INTEGER UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_platform_family_id ON platform (family_id);

-- ---------------------------------------------------------------------------
-- Genres (Action, RPG, …) — shared across platforms
-- ---------------------------------------------------------------------------
CREATE TABLE genre (
    id          SMALLSERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    igdb_id     INTEGER UNIQUE,
    rawg_id     INTEGER UNIQUE
);

-- ---------------------------------------------------------------------------
-- Canonical game (one row per title; platform-specific data on game_platform)
-- ---------------------------------------------------------------------------
CREATE TABLE game (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    summary         TEXT,
    storyline       TEXT,
    first_release_date DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_game_name_lower ON game (lower(name));

-- ---------------------------------------------------------------------------
-- External IDs (IGDB, RAWG, Steam appid, …)
-- ---------------------------------------------------------------------------
CREATE TABLE game_external_id (
    id          BIGSERIAL PRIMARY KEY,
    game_id     UUID NOT NULL REFERENCES game (id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    UNIQUE (source, external_id)
);

CREATE INDEX idx_game_external_id_game ON game_external_id (game_id);

-- ---------------------------------------------------------------------------
-- Game ↔ genre
-- ---------------------------------------------------------------------------
CREATE TABLE game_genre (
    game_id     UUID NOT NULL REFERENCES game (id) ON DELETE CASCADE,
    genre_id    SMALLINT NOT NULL REFERENCES genre (id) ON DELETE CASCADE,
    PRIMARY KEY (game_id, genre_id)
);

CREATE INDEX idx_game_genre_genre ON game_genre (genre_id);

-- ---------------------------------------------------------------------------
-- Release / scores per platform (recommendations filter here)
-- ---------------------------------------------------------------------------
CREATE TABLE game_platform (
    game_id             UUID NOT NULL REFERENCES game (id) ON DELETE CASCADE,
    platform_id         SMALLINT NOT NULL REFERENCES platform (id) ON DELETE CASCADE,
    release_date        DATE,
    store_url           TEXT,
    rating_user         REAL,
    rating_critic       REAL,
    rating_total        REAL,
    metacritic_score    SMALLINT,
    rating_story        REAL,
    rating_graphics     REAL,
    rating_action       REAL,
    rawg_rating         REAL,
    last_synced_at      TIMESTAMPTZ,
    source              TEXT,
    PRIMARY KEY (game_id, platform_id)
);

CREATE INDEX idx_game_platform_platform_total
    ON game_platform (platform_id, rating_total DESC NULLS LAST);

CREATE INDEX idx_game_platform_platform_critic
    ON game_platform (platform_id, rating_critic DESC NULLS LAST);

-- ---------------------------------------------------------------------------
-- Text chunks + vectors (summaries, store descriptions, future ingest)
-- ---------------------------------------------------------------------------
CREATE TABLE game_chunk (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id         UUID NOT NULL REFERENCES game (id) ON DELETE CASCADE,
    platform_id     SMALLINT REFERENCES platform (id) ON DELETE SET NULL,
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    content         TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    embedding       vector(1536),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, platform_id, chunk_index)
);

CREATE INDEX idx_game_chunk_game ON game_chunk (game_id);

-- IVFFlat or HNSW after you have enough rows; HNSW is fine for dev scale.
CREATE INDEX idx_game_chunk_embedding_hnsw
    ON game_chunk USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Ingestion job audit
-- ---------------------------------------------------------------------------
CREATE TABLE ingestion_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    stats           JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT
);

CREATE INDEX idx_ingestion_run_source_started ON ingestion_run (source, started_at DESC);

-- ---------------------------------------------------------------------------
-- Seed platform families (expand via ingest from IGDB/RAWG)
-- ---------------------------------------------------------------------------
INSERT INTO platform_family (slug, name) VALUES
    ('playstation', 'PlayStation'),
    ('xbox', 'Xbox'),
    ('pc', 'PC'),
    ('nintendo', 'Nintendo'),
    ('mobile', 'Mobile'),
    ('other', 'Other')
ON CONFLICT (slug) DO NOTHING;
