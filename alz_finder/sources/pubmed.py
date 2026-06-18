"""PubMed via NCBI E-utilities (esearch + efetch).

Best source for clinical case reports. We restrict to the "Case Reports"
publication type when the profile asks for it.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from ._http import get
from ..normalize import Paper, clean_doi

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NAME = "pubmed"


def _key_params() -> dict:
    params = {"tool": "alz-finder", "email": os.environ.get("CONTACT_EMAIL", "")}
    if os.environ.get("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    return params


def search(query: str, limit: int, from_year: int | None,
           filters: dict, profile: str) -> list[Paper]:
    term = query
    if filters.get("case_reports_only"):
        term = f"({query}) AND Case Reports[Publication Type]"
    if from_year:
        term = f"({term}) AND {from_year}:3000[Date - Publication]"

    params = {"db": "pubmed", "term": term, "retmax": limit, "retmode": "json"}
    params.update(_key_params())
    ids = get(ESEARCH, params=params).json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    fetch_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
    fetch_params.update(_key_params())
    xml = get(EFETCH, params=fetch_params).text
    return _parse(xml, profile)


def _parse(xml: str, profile: str) -> list[Paper]:
    out: list[Paper] = []
    root = ET.fromstring(xml)
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID", default="")
        title = art.findtext(".//ArticleTitle", default="").strip()
        abstract = " ".join(
            (n.text or "") for n in art.findall(".//Abstract/AbstractText")
        ).strip()
        year = art.findtext(".//JournalIssue/PubDate/Year") or \
            art.findtext(".//JournalIssue/PubDate/MedlineDate", "")[:4]
        venue = art.findtext(".//Journal/Title", default="")
        authors = "; ".join(
            f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
            for a in art.findall(".//Author") if a.find("LastName") is not None
        )
        doi = ""
        pmcid = ""
        for idn in art.findall(".//ArticleId"):
            if idn.get("IdType") == "doi":
                doi = clean_doi(idn.text)
            elif idn.get("IdType") == "pmc":
                pmcid = (idn.text or "").strip()
        pub_types = "; ".join(
            pt.text for pt in art.findall(".//PublicationType") if pt.text
        )
        out.append(Paper(
            source=NAME, source_id=pmid, title=title, abstract=abstract,
            authors=authors, year=int(year) if str(year).isdigit() else None,
            venue=venue, doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            pub_types=pub_types, profile=profile,
            pmcid=pmcid, oa_status="open" if pmcid else "",
        ))
    return out
