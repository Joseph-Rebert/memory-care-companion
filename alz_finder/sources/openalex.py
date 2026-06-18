"""OpenAlex works search — broad, free, rich metadata, no key needed."""
from __future__ import annotations

import os

from ._http import get
from ..normalize import Paper, clean_doi

API = "https://api.openalex.org/works"
NAME = "openalex"


def _reconstruct_abstract(inv_index: dict | None) -> str:
    if not inv_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def search(query: str, limit: int, from_year: int | None,
           filters: dict, profile: str) -> list[Paper]:
    params = {"search": query, "per-page": min(limit, 200)}
    if from_year:
        params["filter"] = f"from_publication_date:{from_year}-01-01"
    if os.environ.get("CONTACT_EMAIL"):
        params["mailto"] = os.environ["CONTACT_EMAIL"]

    results = get(API, params=params).json().get("results", [])
    out: list[Paper] = []
    for r in results[:limit]:
        authors = "; ".join(
            a.get("author", {}).get("display_name", "")
            for a in r.get("authorships", [])
        )
        loc = (r.get("primary_location") or {})
        out.append(Paper(
            source=NAME, source_id=r.get("id", "").rsplit("/", 1)[-1],
            title=(r.get("title") or "").strip(),
            abstract=_reconstruct_abstract(r.get("abstract_inverted_index")),
            authors=authors,
            year=r.get("publication_year"),
            venue=(loc.get("source") or {}).get("display_name", "") if loc else "",
            doi=clean_doi(r.get("doi")),
            url=r.get("id", ""),
            pdf_url=(r.get("open_access") or {}).get("oa_url", "") or "",
            pub_types=r.get("type", ""),
            profile=profile,
        ))
    return out
