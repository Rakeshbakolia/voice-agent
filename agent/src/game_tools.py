"""LiveKit tools backed by the game catalog database."""

from __future__ import annotations

import logging
from typing import Optional

from catalog.chat_tools import (
    run_get_game_details,
    run_list_catalog_filters,
    run_search_games,
    run_search_similar_games,
)
from catalog.queries import SortDimension
from livekit.agents import RunContext, function_tool

logger = logging.getLogger("agent")


@function_tool
async def search_games_tool(
    context: RunContext,
    platform: str,
    genre: Optional[str] = None,
    sort_by: SortDimension = "total",
    limit: int = 5,
    min_rating: Optional[float] = None,
) -> str:
    """Find top-rated video games for a platform, optionally filtered by genre.

    Use this when the user asks for recommendations, best games, top RPGs, etc.

    Args:
        platform: Platform slug or alias (e.g. ps5, ps4, nintendo-switch, pc, steam).
        genre: Optional genre slug or alias (e.g. rpg, action, adventure, shooter).
        sort_by: Rating column: total, critic, user, story, graphics, or action.
        limit: How many titles to return (1 to 15).
        min_rating: Optional minimum score on the chosen sort column.
    """
    logger.info(
        "search_games platform=%s genre=%s sort_by=%s limit=%s",
        platform,
        genre,
        sort_by,
        limit,
    )
    return run_search_games(
        platform=platform,
        genre=genre,
        sort_by=sort_by,
        limit=limit,
        min_rating=min_rating,
    )


@function_tool
async def get_game_details_tool(
    context: RunContext,
    title: str,
    platform: Optional[str] = None,
) -> str:
    """Look up one game by title for plot, platforms, genres, and scores.

    Use when the user names a specific game or asks what a game is about.

    Args:
        title: Game name or partial name.
        platform: Optional platform slug to scope ratings (e.g. ps5).
    """
    logger.info("get_game_details title=%s platform=%s", title, platform)
    return run_get_game_details(title=title, platform=platform)


@function_tool
async def search_similar_games_tool(
    context: RunContext,
    query: str,
    platform: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Find games by vibe, theme, or description (semantic / RAG search).

    Use when the user describes mood or plot (co-op survival, soulslike, cozy farming)
    rather than only genre and platform rankings.

    Args:
        query: Natural language description of the kind of game they want.
        platform: Optional platform slug to scope results (e.g. ps5, switch).
        limit: Number of titles (1 to 15).
    """
    logger.info("search_similar query=%s platform=%s", query, platform)
    return run_search_similar_games(query=query, platform=platform, limit=limit)


@function_tool
async def list_catalog_filters_tool(context: RunContext) -> str:
    """List example platform and genre slugs stored in the database.

    Use when the user is unsure which platform or genre names work.
    """
    return run_list_catalog_filters()
