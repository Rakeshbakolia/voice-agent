"""FastAPI server for streaming Game Guide text chat."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from catalog.chat_stream import ChatStreamEvent, stream_game_guide_chat

app = FastAPI(title="Game Guide Chat API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


def _format_sse(event: ChatStreamEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    payload = [{"role": m.role, "content": m.content} for m in request.messages]

    def generate() -> Any:
        for event in stream_game_guide_chat(payload):
            yield _format_sse(event)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    import uvicorn

    host = "127.0.0.1"
    port = int(__import__("os").getenv("CHAT_API_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
