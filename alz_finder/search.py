"""Orchestrator: run a profile's sources, dedupe, and store."""
from __future__ import annotations

import importlib

from .config import get_profile
from .normalize import Paper
from .relevance import is_case_report
from .store import Store

# Map source name in config -> module under alz_finder.sources
_SOURCE_MODULES = {
    "pubmed": "pubmed",
    "europepmc": "europepmc",
    "openalex": "openalex",
    "arxiv": "arxiv",
    "semantic_scholar": "semantic_scholar",
}


def _load_source(name: str):
    if name not in _SOURCE_MODULES:
        raise KeyError(f"unknown source '{name}'")
    return importlib.import_module(f".sources.{_SOURCE_MODULES[name]}", package="alz_finder")


def run_profile(cfg: dict, profile_name: str, store: Store,
                limit: int | None = None) -> dict:
    """Execute every source in the profile. Returns a per-source report."""
    profile = get_profile(cfg, profile_name)
    defaults = cfg.get("defaults", {})
    per_source = limit or defaults.get("per_source_limit", 25)
    from_year = defaults.get("from_year")
    query = " ".join(profile["query"].split())  # collapse YAML folding whitespace
    filters = profile.get("filters", {})

    require_case_report = filters.get("case_reports_only", False)

    report: dict = {"profile": profile_name, "sources": {}, "new": 0,
                    "updated": 0, "dropped": 0}
    for src_name in profile.get("sources", []):
        try:
            module = _load_source(src_name)
            papers: list[Paper] = module.search(
                query, per_source, from_year, filters, profile_name
            )
        except Exception as exc:  # one bad source shouldn't kill the run
            report["sources"][src_name] = {"error": str(exc)}
            continue

        new = updated = dropped = 0
        for p in papers:
            # Guarantee: when a profile asks for case reports only, drop anything
            # the source did not actually tag as a case report.
            if require_case_report and not is_case_report(p):
                dropped += 1
                continue
            _, is_new = store.upsert(p)
            if is_new:
                new += 1
            else:
                updated += 1
        report["sources"][src_name] = {
            "fetched": len(papers), "new": new, "updated": updated, "dropped": dropped
        }
        report["new"] += new
        report["updated"] += updated
        report["dropped"] += dropped
    return report
