"""Unified paper record and dedup key.

Every source module returns a list of ``Paper`` objects so the rest of the
pipeline can treat results from PubMed, arXiv, etc. identically.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, asdict


def _clean_text(s: str) -> str:
    """Unescape HTML entities and strip inline tags some APIs embed in text."""
    if not s:
        return s
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", "", s)           # strip <i>, <sub>, etc.
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Paper:
    source: str                 # e.g. "pubmed", "arxiv"
    source_id: str              # the source's native id (PMID, arXiv id, ...)
    title: str
    abstract: str = ""
    authors: str = ""           # "Last F; Last F" joined string
    year: int | None = None
    venue: str = ""             # journal / conference
    doi: str = ""
    url: str = ""               # canonical landing page
    pdf_url: str = ""           # direct full-text/PDF link when known
    pub_types: str = ""         # e.g. "Case Reports; Journal Article"
    profile: str = ""           # search profile that produced this record
    pmcid: str = ""             # PubMed Central id (enables OA full-text fetch)
    oa_status: str = ""         # "open" | "closed" | "" (unknown)

    def __post_init__(self) -> None:
        self.title = _clean_text(self.title)
        self.abstract = _clean_text(self.abstract)

    def dedup_key(self) -> str:
        """Stable identity across sources.

        Prefer a normalized DOI; fall back to a hash of the normalized title.
        This lets the same paper found via two APIs collapse into one row.
        """
        if self.doi:
            return "doi:" + self.doi.strip().lower()
        return "title:" + _hash_title(self.title)

    def to_row(self) -> dict:
        return asdict(self)


def _hash_title(title: str) -> str:
    norm = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def clean_doi(doi: str | None) -> str:
    """Strip URL prefixes so DOIs from different sources match."""
    if not doi:
        return ""
    doi = doi.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.lower()
