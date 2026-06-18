"""Streamlit web chat: Memory Care Companion — Alzheimer's caregiver assistant (with RAG).

Run from the project root:
    streamlit run chatbot/app.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st

from alz_finder.config import load_env
from chatbot.claude_client import DEFAULT_MODEL, MODELS, stream_reply
from chatbot import knowledge
from chatbot.prompts import DISCLAIMER

st.set_page_config(page_title="Memory Care Companion", page_icon="🧠")
load_env()

st.title("🧠 Memory Care Companion")
st.caption(DISCLAIMER)

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("No `ANTHROPIC_API_KEY` found. Copy `.env.example` to `.env`, paste "
             "your key, and reload.")
    st.stop()


def _load_state():
    """(Re)load the vector index and the stuff-all fallback knowledge."""
    st.session_state.index = knowledge.load_index()
    st.session_state.full_text, st.session_state.full_sources = knowledge.load_knowledge()


if "index" not in st.session_state:
    _load_state()
st.session_state.setdefault("messages", [])
st.session_state.setdefault("last_usage", None)
st.session_state.setdefault("last_sources", [])

# RAG is on only when we have both an index and a Voyage key to embed queries.
rag_on = bool(st.session_state.index) and bool(os.environ.get("VOYAGE_API_KEY"))

# --- Sidebar --------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    model_label = st.selectbox("Model", list(MODELS),
                               index=list(MODELS.values()).index(DEFAULT_MODEL))
    model = MODELS[model_label]

    if rag_on:
        n = len(st.session_state.index["items"])
        st.metric("Indexed cases", n)
        k = st.slider("Cases to retrieve (top-k)", 1, min(10, max(1, n)),
                      min(5, n))
        st.caption(f"🔎 RAG on · {st.session_state.index['model']}")
    else:
        k = None
        st.metric("Cases (all sent)", len(st.session_state.full_sources))
        st.warning("Retrieval off — sending all cases. Build the index:\n\n"
                   "`python -m alz_finder.cli build-embeddings`\n\n"
                   "(and set `VOYAGE_API_KEY` in `.env`), then Refresh.")

    if st.button("🔄 Refresh knowledge"):
        _load_state()
        st.rerun()
    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.session_state.last_usage = None
        st.session_state.last_sources = []
        st.rerun()

    label = "Cases used in last answer" if rag_on else "All cases"
    shown = st.session_state.last_sources if rag_on else st.session_state.full_sources
    with st.expander(f"{label} ({len(shown)})"):
        if not shown:
            st.write("Ask a question to see which cases were used." if rag_on
                     else "No analyzed cases yet. Run `analyze`.")
        for s in shown:
            sc = f" · {s['score']:.2f}" if "score" in s else ""
            name = f"{s['title']} ({s['year']})" if s.get("year") else s["title"]
            st.markdown(f"- [{name}]({s['url']}){sc}" if s.get("url")
                        else f"- {name}{sc}")

    if st.session_state.last_usage:
        u = st.session_state.last_usage
        st.caption(f"Last reply — in: {u['input_tokens']}, out: "
                   f"{u['output_tokens']}, cache read: {u['cache_read_input_tokens']}")

if not st.session_state.full_sources:
    st.warning("The knowledge base is empty. Run "
               "`python -m alz_finder.cli analyze --profile case-studies --min-score 2`.")

# --- Chat history ---------------------------------------------------------
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- Input + streamed reply ----------------------------------------------
if prompt := st.chat_input("Ask about caring for someone with Alzheimer's…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build grounding: retrieve top-k (RAG) or fall back to all cases.
    sources: list[dict] = []
    if rag_on:
        try:
            knowledge_text, sources = knowledge.retrieve_knowledge(
                prompt, st.session_state.index, k=k)
        except Exception as exc:
            st.warning(f"Retrieval failed ({exc}); using all cases for this answer.")
            knowledge_text = st.session_state.full_text
    else:
        knowledge_text = st.session_state.full_text

    with st.chat_message("assistant"):
        usage: dict = {}
        try:
            reply = st.write_stream(
                stream_reply(model, knowledge_text,
                             st.session_state.messages, usage_out=usage))
        except Exception as exc:
            st.error(f"Sorry — something went wrong calling the model: {exc}")
            st.stop()

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.last_usage = usage or None
    st.session_state.last_sources = sources
    st.rerun()
