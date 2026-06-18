"""Build a retrieval-ready knowledge base (chunked text + metadata) as JSONL.

Each line in cases.jsonl is one chunk:
    {"id": "<paper_id>-c<chunk>", "text": "...", "metadata": {...}}

The KB is embed-ready: you compute embeddings over `text` with the embedding
model of your choice and load into a vector store (see knowledge_base/README.md).
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
KB_DIR = os.path.join(ROOT, "knowledge_base")

CHUNK_WORDS = 600       # ~800 tokens
OVERLAP_WORDS = 80      # context bleed between adjacent chunks


def chunk_text(text: str, size: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    return chunks


def _metadata(row) -> dict:
    return {
        "paper_id": row["id"],
        "title": row["title"],
        "authors": row["authors"],
        "year": row["year"],
        "venue": row["venue"],
        "doi": row["doi"],
        "url": row["url"],
        "source": row["source"],
        "pmcid": row["pmcid"],
        "score": row["score"],
        "matched_dims": row["matched"],
        "text_source": row["text_source"],
        "oa_status": row["oa_status"],
    }


def build_kb(store, profile: str | None, min_score: int | None) -> dict:
    """Write knowledge_base/cases.jsonl. Returns a summary dict."""
    os.makedirs(KB_DIR, exist_ok=True)
    rows = store.list_papers(profile=profile, min_score=min_score)
    cases_path = os.path.join(KB_DIR, "cases.jsonl")

    n_cases = n_chunks = n_fulltext = 0
    with open(cases_path, "w") as fh:
        for row in rows:
            body = row["full_text"] if row["text_source"] != "abstract" and row["full_text"] \
                else row["abstract"]
            if not body:
                continue
            n_cases += 1
            if row["text_source"] != "abstract":
                n_fulltext += 1
            meta = _metadata(row)
            for i, chunk in enumerate(chunk_text(body)):
                rec = {"id": f"{row['id']}-c{i}", "text": chunk, "metadata": meta}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_chunks += 1

    # Optionally fold in the distilled analysis as additional retrievable records.
    analysis_path = os.path.join(KB_DIR, "analysis.jsonl")
    n_analysis = 0
    if os.path.exists(analysis_path):
        with open(analysis_path) as src, open(cases_path, "a") as fh:
            for line in src:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                text = rec.get("summary_text") or json.dumps(rec, ensure_ascii=False)
                meta = {"paper_id": rec.get("paper_id"), "title": rec.get("title"),
                        "text_source": "analysis", "kind": "distilled_analysis"}
                fh.write(json.dumps(
                    {"id": f"{rec.get('paper_id')}-analysis", "text": text,
                     "metadata": meta}, ensure_ascii=False) + "\n")
                n_analysis += 1

    return {"path": cases_path, "cases": n_cases, "chunks": n_chunks,
            "fulltext_cases": n_fulltext, "analysis_records": n_analysis}
