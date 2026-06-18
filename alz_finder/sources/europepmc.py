"""Europe PMC REST search.

Good complement to PubMed: includes preprints and surfaces open-access
full-text links. Supports a PUB_TYPE filter for case reports.
"""
from __future__ import annotations

from ._http import get
from ..normalize import Paper, clean_doi

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NAME = "europepmc"


def search(query: str, limit: int, from_year: int | None,
           filters: dict, profile: str) -> list[Paper]:
    q = query
    if filters.get("case_reports_only"):
        q = f"({query}) AND PUB_TYPE:\"Case Reports\""
    if filters.get("open_access_only"):
        q = f"({q}) AND OPEN_ACCESS:Y"
    if from_year:
        q = f"({q}) AND (PUB_YEAR:[{from_year} TO 3000])"

    params = {"query": q, "format": "json", "pageSize": min(limit, 100),
              "resultType": "core"}
    results = get(API, params=params).json().get("resultList", {}).get("result", [])
    return [_parse_result(r, profile) for r in results[:limit]]


def _parse_result(r: dict, profile: str) -> Paper:
    # Prefer an open-access PDF (render) link, then any open-access link.
    oa_pdf = oa_any = ""
    for ft in r.get("fullTextUrlList", {}).get("fullTextUrl", []):
        if ft.get("availability") != "Open access":
            continue
        if ft.get("documentStyle") == "pdf":
            oa_pdf = ft.get("url", "")
        elif not oa_any:
            oa_any = ft.get("url", "")
    ft_url = oa_pdf or oa_any

    authors = "; ".join(
        a.get("fullName", "") for a in r.get("authorList", {}).get("author", [])
    )
    pmid = r.get("pmid", "")
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else \
        f"https://europepmc.org/article/{r.get('source','MED')}/{r.get('id','')}"
    return Paper(
        source=NAME, source_id=str(r.get("id", "")),
        title=(r.get("title") or "").strip(),
        abstract=(r.get("abstractText") or "").strip(),
        authors=authors,
        year=int(r["pubYear"]) if str(r.get("pubYear", "")).isdigit() else None,
        venue=r.get("journalTitle", ""),
        doi=clean_doi(r.get("doi")),
        url=url, pdf_url=ft_url,
        pub_types="; ".join(r.get("pubTypeList", {}).get("pubType", [])),
        profile=profile,
        pmcid=r.get("pmcid", "") or "",
        oa_status="open" if r.get("isOpenAccess") == "Y" else "closed",
    )


def fetch_by_id(kind: str, value: str, profile: str) -> Paper | None:
    """Look up a single article by DOI, PMCID, or PMID. Returns None if not found."""
    if kind == "doi":
        q = f'DOI:"{value}"'
    elif kind == "pmcid":
        q = f"PMCID:{value}"
    elif kind == "pmid":
        q = f"EXT_ID:{value} AND SRC:MED"
    else:
        return None
    params = {"query": q, "format": "json", "pageSize": 1, "resultType": "core"}
    results = get(API, params=params).json().get("resultList", {}).get("result", [])
    return _parse_result(results[0], profile) if results else None
