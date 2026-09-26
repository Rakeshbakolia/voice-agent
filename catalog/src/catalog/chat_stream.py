"""OpenAI Chat Completions streaming with catalog tool calling."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

import certifi

from catalog.chat_prompt import GAME_GUIDE_TEXT_SYSTEM_PROMPT
from catalog.chat_tools import OPENAI_TOOL_DEFINITIONS, execute_tool_call

DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOOL_ROUNDS = 6


@dataclass
class ChatStreamEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


def _api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return key


def _model() -> str:
    return os.getenv("OPENAI_CHAT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _post_chat(body: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(request, timeout=120, context=ssl_ctx) as response:
            if body.get("stream"):
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    yield json.loads(data)
            else:
                yield json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI chat HTTP {exc.code}: {detail[:800]}") from exc


def _normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role in ("user", "assistant", "system") and content is not None:
            out.append({"role": role, "content": str(content)})
    return out[-40:]


def stream_game_guide_chat(
    messages: list[dict[str, str]],
) -> Generator[ChatStreamEvent, None, None]:
    """Yield SSE-ready events: token, tool_start, tool_end, error, done."""
    conversation: list[dict[str, Any]] = [
        {"role": "system", "content": GAME_GUIDE_TEXT_SYSTEM_PROMPT},
        *_normalize_messages(messages),
    ]

    for _round in range(MAX_TOOL_ROUNDS):
        body = {
            "model": _model(),
            "messages": conversation,
            "tools": OPENAI_TOOL_DEFINITIONS,
            "stream": True,
        }

        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, str]] = {}
        finish_reason: Optional[str] = None

        try:
            for chunk in _post_chat(body):
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                finish_reason = choice.get("finish_reason") or finish_reason

                if delta.get("content"):
                    text = str(delta["content"])
                    content_parts.append(text)
                    yield ChatStreamEvent("token", {"text": text})

                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index", 0))
                    entry = tool_calls.setdefault(
                        idx, {"id": "", "name": "", "arguments": ""}
                    )
                    if tc.get("id"):
                        entry["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        entry["name"] = fn["name"]
                    if fn.get("arguments"):
                        entry["arguments"] += fn["arguments"]
        except RuntimeError as exc:
            yield ChatStreamEvent("error", {"message": str(exc)})
            yield ChatStreamEvent("done", {})
            return

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts)}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tool_calls[i]["id"],
                    "type": "function",
                    "function": {
                        "name": tool_calls[i]["name"],
                        "arguments": tool_calls[i]["arguments"],
                    },
                }
                for i in sorted(tool_calls)
            ]
        conversation.append(assistant_msg)

        if finish_reason != "tool_calls" and not tool_calls:
            yield ChatStreamEvent("done", {})
            return

        if not tool_calls:
            yield ChatStreamEvent("done", {})
            return

        for i in sorted(tool_calls):
            tc = tool_calls[i]
            name = tc["name"]
            yield ChatStreamEvent("tool_start", {"name": name})
            result = execute_tool_call(name, tc["arguments"])
            yield ChatStreamEvent("tool_end", {"name": name})
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }
            )

    yield ChatStreamEvent(
        "error",
        {"message": "Too many tool rounds; please try a simpler question."},
    )
    yield ChatStreamEvent("done", {})
