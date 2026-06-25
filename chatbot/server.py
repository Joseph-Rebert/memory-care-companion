"""FastAPI web server: Memory Care Companion — Alzheimer's caregiver assistant (with RAG).

Run from the project root:
    uvicorn chatbot.server:app --reload
or:
    python -m chatbot.server

Serves a static chat UI (chatbot/static/) and a streaming chat API.

The server is stateless: the browser holds the conversation and sends the full
message list with each request, so this scales horizontally and needs no session
store. The vector index is loaded once at startup.
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from alz_finder.config import load_env
from chatbot import knowledge
from chatbot.claude_client import stream_reply
from chatbot.prompts import DISCLAIMER

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")

# Single fixed model — keeps the UI clean (no picker) and answers consistent.
MODEL = "claude-sonnet-4-6"
DEFAULT_K = 5

load_env()

app = FastAPI(title="Memory Care Companion")

# In-process state, loaded once at startup (the vector index + fallback text).
STATE: dict = {"index": None, "full_text": "", "full_sources": []}


def _load_state() -> None:
    STATE["index"] = knowledge.load_index()
    STATE["full_text"], STATE["full_sources"] = knowledge.load_knowledge()


def _rag_on() -> bool:
    """RAG works only with both an index and a Voyage key to embed queries."""
    return bool(STATE["index"]) and bool(os.environ.get("VOYAGE_API_KEY"))


@app.on_event("startup")
def _startup() -> None:
    _load_state()


# --- API ------------------------------------------------------------------
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@app.get("/api/config")
def config() -> dict:
    """Everything the UI needs to render."""
    rag = _rag_on()
    return {
        "disclaimer": DISCLAIMER,
        "rag_on": rag,
        "total_cases": len(STATE["full_sources"]),
        "all_sources": STATE["full_sources"],
        "has_api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.post("/api/reload")
def reload_knowledge() -> dict:
    """Re-read the analyses and vector index from disk (after a rebuild)."""
    _load_state()
    return config()


def _sse(event_type: str, **data) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


@app.post("/api/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Stream a grounded reply as Server-Sent Events.

    Event types: 'sources' (cases used), 'delta' (text chunk), 'usage' (tokens),
    'done', and 'error'.
    """
    messages = [m.model_dump() for m in req.messages]

    # Latest user turn is the retrieval query.
    query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    def gen():
        if not os.environ.get("ANTHROPIC_API_KEY"):
            yield _sse("error", message="No ANTHROPIC_API_KEY configured on the server.")
            return

        # Build grounding: retrieve top-k (RAG) or fall back to all cases.
        sources: list[dict] = []
        if _rag_on():
            try:
                knowledge_text, sources = knowledge.retrieve_knowledge(
                    query, STATE["index"], k=DEFAULT_K)
            except Exception as exc:  # retrieval failure -> stuff everything
                knowledge_text = STATE["full_text"]
                yield _sse("notice", message=f"Retrieval failed ({exc}); using all cases.")
        else:
            knowledge_text = STATE["full_text"]
            sources = STATE["full_sources"]

        yield _sse("sources", sources=sources)

        try:
            for chunk in stream_reply(MODEL, knowledge_text, messages):
                yield _sse("delta", text=chunk)
        except Exception as exc:
            yield _sse("error", message=f"Model call failed: {exc}")
            return

        yield _sse("done")

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# --- Static UI ------------------------------------------------------------
@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("chatbot.server:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", 8000)), reload=True)
