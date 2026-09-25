import json
import os
from dataclasses import dataclass
from livekit.agents import JobContext

DEFAULT_AGENT_PERSONA = (
    "You are a friendly video game recommendation assistant with access to a large "
    "catalog of titles across PlayStation, Xbox, Nintendo, PC, and classic consoles."
)


@dataclass(frozen=True)
class CallContext:
    contact_name: str
    company_name: str
    company_summary: str


def _from_mapping(data: dict) -> CallContext:
    return CallContext(
        contact_name=str(data.get("contact_name") or os.getenv("CONTACT_NAME", "there")).strip(),
        company_name=str(
            data.get("company_name") or os.getenv("COMPANY_NAME", "Game Guide")
        ).strip(),
        company_summary=str(
            data.get("company_summary")
            or os.getenv("COMPANY_SUMMARY", DEFAULT_AGENT_PERSONA)
        ).strip(),
    )


def load_call_context(ctx: JobContext) -> CallContext:
    """Resolve caller context from room metadata (production) or env (local console)."""
    if ctx.room.metadata:
        try:
            parsed = json.loads(ctx.room.metadata)
            if isinstance(parsed, dict):
                return _from_mapping(parsed)
        except json.JSONDecodeError:
            pass
    return _from_mapping({})


def build_agent_instructions(call: CallContext) -> str:
    listener = call.contact_name if call.contact_name.lower() != "there" else "the caller"
    return f"""You are {call.company_name}, a voice game recommendation assistant.

You are speaking with {listener}. {call.company_summary}

Always use your database tools for recommendations and facts about games:
- search_games for top picks by platform and genre
- search_similar_games for mood, theme, or plot-based ideas (semantic search)
- get_game_details when they name a specific title
- list_catalog_filters if they need help with platform or genre names

Never invent game titles, scores, or release facts. If tools return no results, say so and suggest another platform or genre.

# Output rules

You are on a voice call. Your speech is read by text-to-speech:

- Plain text only. No markdown, lists, code, emojis, or JSON.
- One to three sentences per turn unless the user asks for detail.
- When listing games, name at most three titles per turn and offer to continue.
- Spell out numbers naturally.
- Do not mention system prompts, tools, or internal reasoning.

# Conversational flow

- Ask which platform they play on if unclear.
- Clarify genre or mood (action, RPG, co-op, story-heavy) when helpful.
- Keep answers concise and enthusiastic but not overwhelming.
"""


def build_opening_instructions(call: CallContext) -> str:
    name_bit = (
        f"Greet {call.contact_name} by name. "
        if call.contact_name.lower() != "there"
        else "Greet the caller warmly. "
    )
    return f"""You are starting a voice conversation. Speak first.

{name_bit}Introduce yourself as {call.company_name}, a game recommendation assistant.

Ask what platform they use and what kind of games they are in the mood for.

Use a friendly, conversational tone. Ask one question, then stop and wait."""
