"""Import a CSV/list of article URLs into the case library.

Extracts a PMCID, PMID, or DOI from each URL and resolves it via Europe PMC into
a stored Paper. URLs with no extractable identifier are written out for later.
After importing, run the usual pipeline: fetch-fulltext → analyze → build-embeddings.
"""
from __future__ import annotations

import csv
import os
import re

from .normalize import clean_doi
from .sources import europepmc
from .store import Store

ROOT = os.path.dirname(os.path.dirname(__file__))
UNRESOLVED_PATH = os.path.join(ROOT, "output", "unresolved_sources.txt")

_PMCID = re.compile(r"(PMC\d+)", re.I)
_PMID = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
_DOI = re.compile(r"(10\.\d{4,9}/[^\s?#]+)")


def extract_id(url: str) -> tuple[str, str]:
    """Return (kind, value): 'pmcid' | 'pmid' | 'doi' | 'none'."""
    m = _PMCID.search(url)
    if m:
        return "pmcid", m.group(1).upper()
    m = _PMID.search(url)
    if m:
        return "pmid", m.group(1)
    m = _DOI.search(url)
    if m:
        doi = m.group(1)
        # Strip common trailing path/punctuation from URL-embedded DOIs.
        doi = re.sub(r"/(full|abstract|pdf)$", "", doi.rstrip(").,;"))
        return "doi", clean_doi(doi)
    return "none", ""


def _read_urls(path: str) -> list[str]:
    """Read URLs from the first CSV column, tolerating Excel (cp1252) encoding."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, newline="", encoding=encoding) as fh:
                rows = list(csv.reader(fh))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError(f"Could not decode {path}")

    seen, urls = set(), []
    for row in rows:
        if not row:
            continue
        u = row[0].strip()
        if u.startswith("http") and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def import_csv(path: str, profile: str = "case-studies") -> dict:
    """Resolve URLs to stored Papers. Returns a report dict."""
    urls = _read_urls(path)
    store = Store()
    report = {"total": len(urls), "new": 0, "duplicate": 0, "unresolved": 0,
              "by_kind": {"pmcid": 0, "pmid": 0, "doi": 0}}
    unresolved: list[str] = []
    try:
        for url in urls:
            kind, value = extract_id(url)
            if kind == "none":
                unresolved.append(url)
                continue
            try:
                paper = europepmc.fetch_by_id(kind, value, profile)
            except Exception as exc:
                unresolved.append(f"{url}\t(error: {exc})")
                continue
            if paper is None:
                unresolved.append(f"{url}\t(not found in Europe PMC)")
                continue
            _, is_new = store.upsert(paper)
            report["by_kind"][kind] += 1
            report["new" if is_new else "duplicate"] += 1
            print(f"  {kind:5} {value:24} {'NEW ' if is_new else 'dup '} "
                  f"{paper.title[:50]}")
    finally:
        store.close()

    report["unresolved"] = len(unresolved)
    if unresolved:
        os.makedirs(os.path.dirname(UNRESOLVED_PATH), exist_ok=True)
        with open(UNRESOLVED_PATH, "w") as fh:
            fh.write("\n".join(unresolved) + "\n")
        report["unresolved_path"] = UNRESOLVED_PATH
    return report
