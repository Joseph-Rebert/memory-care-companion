"""Build the chatbot's grounding text from the distilled case analyses.

Two modes:
- retrieve_knowledge(): RAG — embed the question and ground on the top-k most
  relevant cases (preferred; scales as the library grows).
- load_knowledge(): fallback — stuff ALL non-off-topic cases (used when the
  vector index or VOYAGE_API_KEY isn't available).

Both reuse _format_case so citations and formatting are identical.
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(__file__))
ANALYSIS_PATH = os.path.join(ROOT, "knowledge_base", "analysis.jsonl")

_INTRO = ("The following are distilled analyses of real, published Alzheimer's "
          "case reports. Ground your answers in them. Each case carries a "
          "SOURCE_URL — when you draw on a case, cite it as a markdown link "
          "using exactly that URL.\n\n")


def _cite_url(rec: dict) -> str:
    """A URL that actually resolves to the paper, or "" if we don't have one.

    Some records carry a bare host (e.g. "https://pubmed.ncbi.nlm.nih.gov/")
    with no article id. Linking that is worse than not linking — it looks like a
    citation but drops the reader on a homepage — so treat it as missing.
    """
    url = (rec.get("url") or "").strip()
    if url:
        path = re.sub(r"^https?://[^/]+", "", url).strip("/")
        if path:
            return url
    doi = (rec.get("doi") or "").strip()
    return f"https://doi.org/{doi}" if doi else ""


def _format_case(rec: dict) -> str:
    lines = [f"### {rec.get('title', '(untitled)')}"]
    cite = _cite_url(rec)
    lines.append(f"- YEAR: {rec.get('year', 'n.d.')}")
    # Spelled out so the model can copy it verbatim into a markdown link.
    lines.append(f"- SOURCE_URL: {cite}" if cite else "- SOURCE_URL: (none — cite by title only)")
    for field, label in [
        ("patient_profile", "Patient"),
        ("symptoms_behavior", "Symptoms & behavior"),
        ("communication", "Communication"),
        ("progression", "Progression"),
        ("treatment_management", "Treatment & management"),
    ]:
        if rec.get(field):
            lines.append(f"- {label}: {rec[field]}")
    insights = rec.get("caregiver_insights") or []
    if insights:
        lines.append("- Caregiver insights:")
        lines.extend(f"    * {i}" for i in insights)
    qa = rec.get("example_qa") or []
    if qa:
        lines.append("- Example Q&A:")
        for pair in qa:
            lines.append(f"    Q: {pair.get('q', '')}")
            lines.append(f"    A: {pair.get('a', '')}")
    return "\n".join(lines)


def _source(rec: dict, score: float | None = None) -> dict:
    s = {"title": rec.get("title", "(untitled)"), "url": _cite_url(rec),
         "year": rec.get("year"), "relevance": rec.get("caregiver_relevance", "")}
    if score is not None:
        s["score"] = round(score, 3)
    return s


def _build(recs: list[dict], scores: list[float] | None = None) -> tuple[str, list[dict]]:
    if not recs:
        return "", []
    text = _INTRO + "\n\n".join(_format_case(r) for r in recs)
    sources = [_source(r, scores[i] if scores else None) for i, r in enumerate(recs)]
    return text, sources


# --- Fallback: stuff everything ------------------------------------------
def load_knowledge() -> tuple[str, list[dict]]:
    """All non-off-topic cases as one grounding string (no retrieval)."""
    if not os.path.exists(ANALYSIS_PATH):
        return "", []
    recs = []
    with open(ANALYSIS_PATH) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("caregiver_relevance") == "off-topic":
                continue
            recs.append(rec)
    return _build(recs)


# --- RAG: retrieve the top-k relevant cases ------------------------------
def load_index():
    """Load the vector index, or None if it hasn't been built."""
    from alz_finder import embeddings
    return embeddings.load_index()


def retrieve_knowledge(query: str, index, k: int = 5,
                       threshold: float | None = None) -> tuple[str, list[dict]]:
    """Ground on the top-k cases most relevant to `query`."""
    from alz_finder import embeddings
    results = embeddings.search(query, index, k=k, threshold=threshold)
    recs = [item["rec"] for item, _ in results]
    scores = [score for _, score in results]
    return _build(recs, scores)
