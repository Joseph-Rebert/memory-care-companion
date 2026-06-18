"""arXiv Atom API — CS/AI preprints (conversational AI, NLP methods)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from ._http import get
from ..normalize import Paper

API = "https://export.arxiv.org/api/query"
NAME = "arxiv"
ATOM = "{http://www.w3.org/2005/Atom}"


def search(query: str, limit: int, from_year: int | None,
           filters: dict, profile: str) -> list[Paper]:
    # arXiv has no rich boolean date filter; we fetch newest-first and
    # post-filter by year.
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(limit * 2, 100),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    xml = get(API, params=params).text
    root = ET.fromstring(xml)

    out: list[Paper] = []
    for entry in root.findall(f"{ATOM}entry"):
        published = entry.findtext(f"{ATOM}published", "")
        year = int(published[:4]) if published[:4].isdigit() else None
        if from_year and year and year < from_year:
            continue
        arxiv_id = entry.findtext(f"{ATOM}id", "").rsplit("/", 1)[-1]
        pdf_url = ""
        for link in entry.findall(f"{ATOM}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
        authors = "; ".join(
            a.findtext(f"{ATOM}name", "") for a in entry.findall(f"{ATOM}author")
        )
        out.append(Paper(
            source=NAME, source_id=arxiv_id,
            title=(entry.findtext(f"{ATOM}title", "") or "").strip().replace("\n", " "),
            abstract=(entry.findtext(f"{ATOM}summary", "") or "").strip(),
            authors=authors, year=year, venue="arXiv",
            url=entry.findtext(f"{ATOM}id", ""),
            pdf_url=pdf_url, pub_types="Preprint", profile=profile,
        ))
        if len(out) >= limit:
            break
    return out
