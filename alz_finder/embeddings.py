"""Vector index over the distilled case analyses, for RAG retrieval.

Embeds one vector per case (from knowledge_base/analysis.jsonl) with Voyage AI,
stores a normalized matrix + aligned metadata on disk, and provides cosine
search. The chatbot uses this to retrieve only the few most relevant cases per
question instead of sending all of them.

Requires VOYAGE_API_KEY in the environment (loaded from .env).
"""
from __future__ import annotations

import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
KB_DIR = os.path.join(ROOT, "knowledge_base")
ANALYSIS_PATH = os.path.join(KB_DIR, "analysis.jsonl")
VECTORS_PATH = os.path.join(KB_DIR, "index.npz")
META_PATH = os.path.join(KB_DIR, "index_meta.json")

DEFAULT_MODEL = "voyage-3.5"
_BATCH = 128  # Voyage caps inputs per request


def _client():
    import voyageai  # lazy: only needed when actually embedding
    return voyageai.Client()  # reads VOYAGE_API_KEY


def _normalize(arr: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def embed_texts(texts: list[str], input_type: str,
                model: str = DEFAULT_MODEL) -> np.ndarray:
    """Embed a list of texts; returns an L2-normalized (n, dim) float32 matrix."""
    vo = _client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _BATCH):
        res = vo.embed(texts[i:i + _BATCH], model=model, input_type=input_type)
        vectors.extend(res.embeddings)
    return _normalize(np.asarray(vectors, dtype=np.float32))


def _embedding_text(rec: dict) -> str:
    """What a caregiver question should match against, per case."""
    parts = [rec.get("title", ""), rec.get("summary_text", "")]
    parts += rec.get("caregiver_insights") or []
    parts += [qa.get("q", "") for qa in (rec.get("example_qa") or [])]
    return "\n".join(p for p in parts if p)


def _load_cases() -> list[dict]:
    """All non-off-topic analysis records."""
    if not os.path.exists(ANALYSIS_PATH):
        return []
    out = []
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
            out.append(rec)
    return out


def build_index(model: str = DEFAULT_MODEL) -> dict:
    """Embed every case and persist the index. Returns a summary dict."""
    cases = _load_cases()
    if not cases:
        raise RuntimeError(
            "No analyzed cases found. Run `analyze` first to populate "
            "knowledge_base/analysis.jsonl."
        )
    vectors = embed_texts([_embedding_text(c) for c in cases], "document", model)

    os.makedirs(KB_DIR, exist_ok=True)
    np.savez(VECTORS_PATH, vectors=vectors)
    items = [{
        "paper_id": c.get("paper_id"),
        "title": c.get("title", "(untitled)"),
        "url": c.get("url", ""),
        "year": c.get("year"),
        "relevance": c.get("caregiver_relevance", ""),
        "rec": c,  # full record so retrieval can format grounding without re-reading
    } for c in cases]
    with open(META_PATH, "w") as fh:
        json.dump({"model": model, "dim": int(vectors.shape[1]), "items": items},
                  fh, ensure_ascii=False)
    return {"count": len(cases), "dim": int(vectors.shape[1]), "model": model}


def load_index() -> dict | None:
    """Return {'vectors', 'items', 'model'} or None if the index isn't built."""
    if not (os.path.exists(VECTORS_PATH) and os.path.exists(META_PATH)):
        return None
    vectors = np.load(VECTORS_PATH)["vectors"]
    with open(META_PATH) as fh:
        meta = json.load(fh)
    return {"vectors": vectors, "items": meta["items"], "model": meta["model"]}


def search(query: str, index: dict, k: int = 5,
           threshold: float | None = None) -> list[tuple[dict, float]]:
    """Return up to k (item, cosine_score) pairs, highest first."""
    if not index or not len(index["items"]):
        return []
    qvec = embed_texts([query], "query", model=index["model"])[0]
    scores = index["vectors"] @ qvec  # cosine (all normalized)
    order = np.argsort(-scores)[:k]
    results = [(index["items"][i], float(scores[i])) for i in order]
    if threshold is not None:
        results = [(it, s) for it, s in results if s >= threshold]
    return results
