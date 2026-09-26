"""Game catalog tools for text chat and voice agents (no LiveKit dependency)."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from catalog.database import get_session_factory
from catalog.embeddings import embed_query_text
from catalog.queries import (
    SortDimension,
    format_game_details,
    format_search_results,
    format_semantic_results,
    get_game_details,
    list_supported_filters,
    search_games,
    semantic_search_games,
)

OPENAI_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_games",
            "description": "Find top-rated video games for a platform, optionally filtered by genre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Platform slug or alias (ps5, nintendo-switch, pc, steam).",
                    },
                    "genre": {"type": "string", "description": "Optional genre slug (rpg, action)."},
                    "sort_by": {
                        "type": "string",
                        "enum": ["total", "critic", "user", "story", "graphics", "action"],
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 15},
                    "min_rating": {"type": "number"},
                },
                "required": ["platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_games",
            "description": "Semantic search by vibe, theme, or plot description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "platform": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 15},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_game_details",
            "description": "Look up one game by title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "platform": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_catalog_filters",
            "description": "List example platform and genre slugs in the database.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_search_games(
    *,
    platform: str,
    genre: Optional[str] = None,
    sort_by: SortDimension = "total",
    limit: int = 5,
    min_rating: Optional[float] = None,
) -> str:
    with get_session_factory()() as session:
        hits = search_games(
            session,
            platform=platform,
            genre=genre,
            sort_by=sort_by,
            limit=limit,
            min_rating=min_rating,
        )
        return format_search_results(hits, platform_query=platform)


def run_get_game_details(*, title: str, platform: Optional[str] = None) -> str:
    with get_session_factory()() as session:
        details = get_game_details(session, title=title, platform=platform)
        if details is None:
            return (
                f"I could not find '{title}' in the catalog"
                + (f" on {platform}" if platform else "")
                + ". Ask the user to spell the title or try search_games instead."
            )
        return format_game_details(details)


def run_search_similar_games(
    *, query: str, platform: Optional[str] = None, limit: int = 5
) -> str:
    try:
        vector = embed_query_text(query)
    except RuntimeError as exc:
        return (
            f"Semantic search is unavailable: {exc}. "
            "Use search_games for rating-based recommendations instead."
        )
    with get_session_factory()() as session:
        hits = semantic_search_games(session, vector, platform=platform, limit=limit)
        return format_semantic_results(hits, query=query)


def run_list_catalog_filters() -> str:
    with get_session_factory()() as session:
        return list_supported_filters(session)


_TOOL_RUNNERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "search_games": lambda a: run_search_games(
        platform=str(a["platform"]),
        genre=a.get("genre"),
        sort_by=a.get("sort_by") or "total",
        limit=int(a.get("limit") or 5),
        min_rating=a.get("min_rating"),
    ),
    "search_similar_games": lambda a: run_search_similar_games(
        query=str(a["query"]),
        platform=a.get("platform"),
        limit=int(a.get("limit") or 5),
    ),
    "get_game_details": lambda a: run_get_game_details(
        title=str(a["title"]),
        platform=a.get("platform"),
    ),
    "list_catalog_filters": lambda _: run_list_catalog_filters(),
}


def execute_tool_call(name: str, arguments_json: str) -> str:
    runner = _TOOL_RUNNERS.get(name)
    if runner is None:
        return f"Unknown tool: {name}"
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        args = {}
    return runner(args)
