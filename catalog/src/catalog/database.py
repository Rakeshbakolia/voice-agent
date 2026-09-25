import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env.local")
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(".env.local")
load_dotenv(".env")

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://voice_agent:voice_agent@localhost:5434/voice_agent"
)


class Base(DeclarativeBase):
    pass


@lru_cache
def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).replace(
        "postgresql://", "postgresql+psycopg://", 1
    )


def get_engine(echo: bool = False):
    return create_engine(get_database_url(), echo=echo, pool_pre_ping=True)


@lru_cache
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
