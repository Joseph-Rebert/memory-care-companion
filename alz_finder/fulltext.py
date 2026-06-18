"""Fetch open-access full text for a stored case.

Strategy, in order:
  1. Europe PMC full-text XML (clean machine text) for articles in the OA subset.
  2. Otherwise download the OA PDF render and extract text with pypdf.
  3. Otherwise give up (the article is abstract-only by license).

Returns (text, source) where source is one of: "fulltext_xml" | "pdf" | "none".
"""
from __future__ import annotations

import io
import re

from .sources._http import get

EPMC_XML = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC/{pmcid}/fullTextXML"

# A floor below which we treat the result as "didn't really get the body".
_MIN_USEFUL_CHARS = 500


def _strip_xml(xml: str) -> str:
    # Drop reference lists and the article's own metadata front matter noise,
    # then strip tags and collapse whitespace.
    xml = re.sub(r"<ref-list.*?</ref-list>", " ", xml, flags=re.S | re.I)
    xml = re.sub(r"<back.*?</back>", " ", xml, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", xml)
    return re.sub(r"\s+", " ", text).strip()


def _try_xml(pmcid: str) -> str | None:
    try:
        resp = get(EPMC_XML.format(pmcid=pmcid), max_retries=2)
    except Exception:
        return None
    if resp.status_code != 200 or not resp.text:
        return None
    text = _strip_xml(resp.text)
    return text if len(text) >= _MIN_USEFUL_CHARS else None


def _try_pdf(pdf_url: str) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        resp = get(pdf_url, max_retries=2)
    except Exception:
        return None
    ctype = resp.headers.get("Content-Type", "")
    if "pdf" not in ctype.lower() and not resp.content[:4] == b"%PDF":
        return None
    try:
        reader = PdfReader(io.BytesIO(resp.content))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) >= _MIN_USEFUL_CHARS else None


def fetch_fulltext(pmcid: str, pdf_url: str) -> tuple[str, str]:
    """Best-effort open-access full text. Returns (text, source)."""
    if pmcid:
        text = _try_xml(pmcid)
        if text:
            return text, "fulltext_xml"

    # Prefer an explicit OA pdf link; else construct the render URL from the PMCID.
    candidate = pdf_url
    if not candidate and pmcid:
        candidate = f"https://europepmc.org/articles/{pmcid}?pdf=render"
    if candidate:
        text = _try_pdf(candidate)
        if text:
            return text, "pdf"

    return "", "none"
