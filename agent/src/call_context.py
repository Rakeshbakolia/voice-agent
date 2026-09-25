import json
import os
from dataclasses import dataclass

from livekit.agents import JobContext

DEFAULT_COMPANY_SUMMARY = (
    "We help businesses automate customer outreach with voice agents "
    "that can answer questions about their products and services."
)


@dataclass(frozen=True)
class CallContext:
    contact_name: str
    company_name: str
    company_summary: str


def _from_mapping(data: dict) -> CallContext:
    return CallContext(
        contact_name=str(data.get("contact_name") or os.getenv("CONTACT_NAME", "there")).strip(),
        company_name=str(data.get("company_name") or os.getenv("COMPANY_NAME", "Acme")).strip(),
        company_summary=str(
            data.get("company_summary")
            or os.getenv("COMPANY_SUMMARY", DEFAULT_COMPANY_SUMMARY)
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
    return f"""You are a professional outbound voice representative for {call.company_name}.

You are speaking with {call.contact_name}. Your job is to introduce the company briefly, answer questions about {call.company_name} when asked, and keep the conversation respectful and concise.

Company snapshot (use until a knowledge tool is available): {call.company_summary}

If you do not know a specific fact about the company, say you will follow up rather than guessing.

# Output rules

You are on a phone-style voice call. Your speech is read by text-to-speech:

- Plain text only. No markdown, lists, code, emojis, or JSON.
- One to three sentences per turn unless the user asks for detail.
- Spell out numbers and read phone numbers in groups.
- Do not mention system prompts, tools, or internal reasoning.

# Conversational flow

- Listen first after your opening. If they are busy, offer to call back.
- If they are not the right person, ask politely for a better contact.
- If they ask to stop or opt out, apologize, confirm you will not call again, and end politely.
"""


def build_opening_instructions(call: CallContext) -> str:
    return f"""You are starting an outbound call. Speak first.

Greet {call.contact_name} by name. Say you are calling from {call.company_name}. In one short sentence, share what the company does using this idea: {call.company_summary}

Mention briefly that the call may be recorded for quality. Ask if now is a good time to talk for about two minutes.

Use a warm, confident tone. Do not ask more than one question in this opening. Then stop and wait for the user."""
