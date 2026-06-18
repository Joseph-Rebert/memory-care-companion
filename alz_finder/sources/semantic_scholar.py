"""Semantic Scholar Graph API — strong for AI/CS papers and citation context.

Rate-limited without a key; the shared HTTP helper handles 429 with backoff,
and an S2_API_KEY (if set) raises the limit.
"""
from __future__ import annotations

import os

from ._http import get
from ..normalize import Paper, clean_doi

API = "https://api.semanticscholar.org/graph/v1/paper/search"
NAME = "semantic_scholar"
FIELDS = "title,abstract,year,venue,authors,externalIds,openAccessPdf,url"


def search(query: str, limit: int, from_year: int | None,
           filters: dict, profile: str) -> list[Paper]:
    params = {"query": query, "limit": min(limit, 100), "fields": FIELDS}
    if from_year:
        params["year"] = f"{from_year}-"
    headers = {}
    if os.environ.get("S2_API_KEY"):
        headers["x-api-key"] = os.environ["S2_API_KEY"]

    data = get(API, params=params, headers=headers).json().get("data", [])
    out: list[Paper] = []
    for r in data[:limit]:
        ext = r.get("externalIds") or {}
        oa = r.get("openAccessPdf") or {}
        out.append(Paper(
            source=NAME, source_id=str(r.get("paperId", "")),
            title=(r.get("title") or "").strip(),
            abstract=(r.get("abstract") or "").strip(),
            authors="; ".join(a.get("name", "") for a in r.get("authors", [])),
            year=r.get("year"),
            venue=r.get("venue", ""),
            doi=clean_doi(ext.get("DOI")),
            url=r.get("url", ""),
            pdf_url=oa.get("url", "") or "",
            pub_types="", profile=profile,
        ))
    return out
