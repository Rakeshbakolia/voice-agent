import uuid
from datetime import date, datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Float,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    column,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog.database import Base


class PlatformFamily(Base):
    __tablename__ = "platform_family"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    platforms: Mapped[list["Platform"]] = relationship(back_populates="family")


class Platform(Base):
    __tablename__ = "platform"
    __table_args__ = (Index("idx_platform_family_id", "family_id"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    family_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger, ForeignKey("platform_family.id", ondelete="SET NULL")
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    generation: Mapped[Optional[int]] = mapped_column(SmallInteger)
    igdb_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    rawg_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    family: Mapped[Optional["PlatformFamily"]] = relationship(back_populates="platforms")
    game_platforms: Mapped[list["GamePlatform"]] = relationship(
        back_populates="platform"
    )


class Genre(Base):
    __tablename__ = "genre"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    igdb_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    rawg_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)

    game_genres: Mapped[list["GameGenre"]] = relationship(back_populates="genre")


class Game(Base):
    __tablename__ = "game"
    __table_args__ = (Index("idx_game_name_lower", func.lower(column("name"))),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    storyline: Mapped[Optional[str]] = mapped_column(Text)
    first_release_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    external_ids: Mapped[list["GameExternalId"]] = relationship(back_populates="game")
    genres: Mapped[list["GameGenre"]] = relationship(back_populates="game")
    platforms: Mapped[list["GamePlatform"]] = relationship(back_populates="game")
    chunks: Mapped[list["GameChunk"]] = relationship(back_populates="game")


class GameExternalId(Base):
    __tablename__ = "game_external_id"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="game_external_id_source_external_id_key"),
        Index("idx_game_external_id_game", "game_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)

    game: Mapped["Game"] = relationship(back_populates="external_ids")


class GameGenre(Base):
    __tablename__ = "game_genre"
    __table_args__ = (Index("idx_game_genre_genre", "genre_id"),)

    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("genre.id", ondelete="CASCADE"), primary_key=True
    )

    game: Mapped["Game"] = relationship(back_populates="genres")
    genre: Mapped["Genre"] = relationship(back_populates="game_genres")


class GamePlatform(Base):
    __tablename__ = "game_platform"
    __table_args__ = (
        Index(
            "idx_game_platform_platform_total",
            "platform_id",
            desc("rating_total").nulls_last(),
        ),
        Index(
            "idx_game_platform_platform_critic",
            "platform_id",
            desc("rating_critic").nulls_last(),
        ),
    )

    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game.id", ondelete="CASCADE"), primary_key=True
    )
    platform_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("platform.id", ondelete="CASCADE"),
        primary_key=True,
    )
    release_date: Mapped[Optional[date]] = mapped_column(Date)
    store_url: Mapped[Optional[str]] = mapped_column(Text)
    rating_user: Mapped[Optional[float]] = mapped_column(Float)
    rating_critic: Mapped[Optional[float]] = mapped_column(Float)
    rating_total: Mapped[Optional[float]] = mapped_column(Float)
    metacritic_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    rating_story: Mapped[Optional[float]] = mapped_column(Float)
    rating_graphics: Mapped[Optional[float]] = mapped_column(Float)
    rating_action: Mapped[Optional[float]] = mapped_column(Float)
    rawg_rating: Mapped[Optional[float]] = mapped_column(Float)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column()
    source: Mapped[Optional[str]] = mapped_column(Text)

    game: Mapped["Game"] = relationship(back_populates="platforms")
    platform: Mapped["Platform"] = relationship(back_populates="game_platforms")


class GameChunk(Base):
    __tablename__ = "game_chunk"
    __table_args__ = (
        UniqueConstraint(
            "game_id", "platform_id", "chunk_index", name="game_chunk_game_id_platform_id_chunk_index_key"
        ),
        Index("idx_game_chunk_game", "game_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game.id", ondelete="CASCADE"), nullable=False
    )
    platform_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger, ForeignKey("platform.id", ondelete="SET NULL")
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    game: Mapped["Game"] = relationship(back_populates="chunks")


class IngestionRun(Base):
    __tablename__ = "ingestion_run"
    __table_args__ = (
        Index("idx_ingestion_run_source_started", "source", desc("started_at")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column()
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
