"""Anthropic client wrapper: cached knowledge system block + streaming replies."""
from __future__ import annotations

import anthropic

from .prompts import SYSTEM_INSTRUCTIONS

# Default to the most capable model; the UI lets the user pick a cheaper one.
MODELS = {
    "Opus 4.8 — most capable": "claude-opus-4-8",
    "Sonnet 4.6 — faster & cheaper": "claude-sonnet-4-6",
    "Haiku 4.5 — fastest & cheapest": "claude-haiku-4-5",
}
DEFAULT_MODEL = "claude-opus-4-8"
MAX_TOKENS = 2048

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def _system_blocks(knowledge_text: str) -> list[dict]:
    """Stable instructions + the knowledge block, cached as a prefix.

    The knowledge block carries cache_control so it's prompt-cached across turns
    (it's identical every message); only the user turn varies after it.
    """
    return [
        {"type": "text", "text": SYSTEM_INSTRUCTIONS},
        {"type": "text", "text": knowledge_text,
         "cache_control": {"type": "ephemeral"}},
    ]


def stream_reply(model: str, knowledge_text: str, messages: list[dict],
                 usage_out: dict | None = None):
    """Yield response text chunks. Populates usage_out with token usage at the end."""
    client = get_client()
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        system=_system_blocks(knowledge_text),
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
        if usage_out is not None:
            u = stream.get_final_message().usage
            usage_out.update({
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0),
                "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0),
            })
