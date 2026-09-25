"""Unit tests for catalog query helpers (no database required)."""

import uuid

from catalog.queries import (
    GameSearchHit,
    format_search_results,
    resolve_genre_slugs,
    resolve_platform_slugs,
)


def test_resolve_platform_aliases() -> None:
    assert "ps5" in resolve_platform_slugs("PS5")
    assert "playstation5" in resolve_platform_slugs("playstation 5")
    assert resolve_platform_slugs("nintendo-switch") == ("nintendo-switch",)


def test_resolve_genre_aliases() -> None:
    assert "rpg" in resolve_genre_slugs("RPG")
    assert "role-playing" in resolve_genre_slugs("role-playing")


def test_format_search_empty() -> None:
    text = format_search_results([], platform_query="ps5")
    assert "No rated games" in text


def test_format_search_nonempty() -> None:
    hit = GameSearchHit(
        game_id=uuid.uuid4(),
        name="Test Game",
        platform_name="PlayStation 5",
        platform_slug="ps5",
        rating=92.0,
        summary="A great game.",
        genres=("RPG",),
    )
    text = format_search_results([hit], platform_query="ps5")
    assert "Test Game" in text
    assert "92" in text
