"""Command-line interface for Memory Care Companion's case-study toolkit.

Usage:
    python -m alz_finder.cli search  --profile case-studies [--limit 25]
    python -m alz_finder.cli list    [--profile P] [--status unrated|keep|maybe|reject]
    python -m alz_finder.cli tag     <id> keep|maybe|reject|unrated [--note "..."]
    python -m alz_finder.cli note    <id> "free-text note"
    python -m alz_finder.cli export  [--profile P] [--format md|csv] [--status S]
    python -m alz_finder.cli stats
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from .config import load_config, load_env
from .export import export_csv, export_markdown
from .fulltext import fetch_fulltext
from .rag import build_kb
from .search import run_profile
from .store import Store


def _cmd_search(args, store: Store) -> int:
    cfg = load_config()
    before = store.count()
    report = run_profile(cfg, args.profile, store, limit=args.limit)
    print(f"Profile: {report['profile']}")
    for src, info in report["sources"].items():
        if "error" in info:
            print(f"  {src:<18} ERROR: {info['error']}")
        else:
            line = (f"  {src:<18} fetched={info['fetched']:<3} "
                    f"new={info['new']:<3} updated={info['updated']}")
            if info.get("dropped"):
                line += f"  (dropped {info['dropped']} non-case-reports)"
            print(line)
    print(f"Total new: {report['new']}  |  DB now holds {store.count()} papers "
          f"(was {before}).")
    if report.get("dropped"):
        print(f"Dropped {report['dropped']} results that were not tagged as case reports.")
    return 0


def _cmd_list(args, store: Store) -> int:
    rows = store.list_papers(profile=args.profile, status=args.status,
                             min_score=args.min_score)
    if not rows:
        print("No papers match.")
        return 0
    for r in rows:
        yr = r["year"] or "????"
        dims = f" [{r['matched']}]" if r["matched"] else ""
        print(f"[{r['id']:>4}] score {r['score']}/4 ({r['relevance']:<7}) {yr} "
              f"{r['source']:<10} {r['title'][:80]}{dims}")
    print(f"\n{len(rows)} papers (sorted by relevance score, 4 = best).")
    return 0


def _cmd_tag(args, store: Store) -> int:
    ok = store.set_relevance(args.id, args.relevance, note=args.note)
    if not ok:
        print(f"No paper with id {args.id}.", file=sys.stderr)
        return 1
    print(f"Paper {args.id} -> {args.relevance}"
          + (f" (note saved)" if args.note else ""))
    return 0


def _cmd_note(args, store: Store) -> int:
    row = store.conn.execute(
        "SELECT relevance FROM review WHERE paper_id=?", (args.id,)
    ).fetchone()
    if not row:
        print(f"No paper with id {args.id}.", file=sys.stderr)
        return 1
    store.set_relevance(args.id, row["relevance"], note=args.text)
    print(f"Note saved on paper {args.id}.")
    return 0


def _cmd_export(args, store: Store) -> int:
    rows = store.list_papers(profile=args.profile, status=args.status,
                             min_score=args.min_score)
    stamp = date.today().isoformat()
    if args.format == "csv":
        path = export_csv(rows, args.profile, stamp)
    else:
        path = export_markdown(rows, args.profile, stamp)
    print(f"Wrote {len(rows)} papers to {path}")
    return 0


def _cmd_fetch_fulltext(args, store: Store) -> int:
    rows = store.list_papers(profile=args.profile, min_score=args.min_score)
    by_source = {"fulltext_xml": 0, "pdf": 0, "none": 0, "skipped": 0}
    for r in rows:
        # Idempotent: skip cases that already have non-abstract full text.
        if r["text_source"] != "abstract" and r["full_text"]:
            by_source["skipped"] += 1
            continue
        text, src = fetch_fulltext(r["pmcid"], r["pdf_url"])
        if src != "none" and text:
            store.set_fulltext(r["id"], text, src)
            print(f"  [{r['id']:>4}] {src:<12} {len(text):>6} chars  {r['title'][:55]}")
        by_source[src] += 1
    print(f"\nFull text: {by_source['fulltext_xml']} via XML, {by_source['pdf']} via PDF, "
          f"{by_source['none']} abstract-only, {by_source['skipped']} already had it.")
    return 0


def _cmd_build_kb(args, store: Store) -> int:
    summary = build_kb(store, profile=args.profile, min_score=args.min_score)
    print(f"Wrote {summary['chunks']} chunks from {summary['cases']} cases "
          f"({summary['fulltext_cases']} with full text) to {summary['path']}")
    if summary["analysis_records"]:
        print(f"Folded in {summary['analysis_records']} distilled analysis records.")
    return 0


def _cmd_analyze(args, store: Store) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Add it to your .env file "
              "(see .env.example).", file=sys.stderr)
        return 1
    from .analyze import analyze, DEFAULT_MODEL  # lazy: only needs anthropic here
    report = analyze(profile=args.profile, min_score=args.min_score,
                     model=args.model or DEFAULT_MODEL, limit=args.limit)
    print(f"\nAnalyzed {report['analyzed']} new case(s); "
          f"skipped {report['skipped_existing']} already done; "
          f"{report['errors']} error(s).")
    if report["by_relevance"]:
        print("By relevance:", ", ".join(
            f"{k}={v}" for k, v in sorted(report["by_relevance"].items())))
    return 0


def _cmd_import_csv(args, store: Store) -> int:
    from .import_urls import import_csv  # lazy import
    r = import_csv(args.path, profile=args.profile)
    print(f"\nResolved {r['new'] + r['duplicate']} / {r['total']} URLs "
          f"(pmcid {r['by_kind']['pmcid']}, doi {r['by_kind']['doi']}, "
          f"pmid {r['by_kind']['pmid']}).")
    print(f"  new: {r['new']}  |  duplicate: {r['duplicate']}  |  "
          f"unresolved: {r['unresolved']}")
    if r.get("unresolved_path"):
        print(f"  unresolved URLs written to {r['unresolved_path']}")
    return 0


def _cmd_build_embeddings(args, store: Store) -> int:
    if not os.environ.get("VOYAGE_API_KEY"):
        print("VOYAGE_API_KEY is not set. Add it to your .env file "
              "(see .env.example; get a key at https://dash.voyageai.com/api-keys).",
              file=sys.stderr)
        return 1
    from .embeddings import build_index, DEFAULT_MODEL  # lazy: only needs voyageai/numpy
    summary = build_index(model=args.model or DEFAULT_MODEL)
    print(f"Embedded {summary['count']} cases ({summary['dim']}-dim, "
          f"model {summary['model']}). Index written to knowledge_base/.")
    return 0


def _cmd_eval(args, store: Store) -> int:
    from .eval import run_eval, DEFAULT_GOLDEN  # lazy: needs voyageai/numpy
    golden = args.golden or DEFAULT_GOLDEN
    if not os.path.exists(golden):
        print(f"Golden set not found at {golden}.\n"
              f"Create one at eval/golden_set.jsonl or pass --golden <path>.",
              file=sys.stderr)
        return 1
    k_vals = tuple(int(k) for k in args.k.split(",")) if args.k else (1, 3, 5)
    try:
        result = run_eval(golden_path=golden, k_values=k_vals)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if args.output:
        import json as _json
        with open(args.output, "w") as fh:
            _json.dump(result, fh, indent=2, ensure_ascii=False)
        print(f"Full results written to {args.output}")
    return 0


def _cmd_stats(args, store: Store) -> int:
    total = store.count()
    print(f"Total papers: {total}")
    by_profile = store.conn.execute(
        "SELECT profile, COUNT(*) n FROM papers GROUP BY profile"
    ).fetchall()
    for r in by_profile:
        print(f"  profile {r['profile'] or '(none)':<14} {r['n']}")
    by_rel = store.conn.execute(
        "SELECT relevance, COUNT(*) n FROM review GROUP BY relevance"
    ).fetchall()
    for r in by_rel:
        print(f"  relevance {r['relevance']:<12} {r['n']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="alz_finder", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="run a search profile")
    s.add_argument("--profile", required=True)
    s.add_argument("--limit", type=int, default=None, help="results per source")
    s.set_defaults(func=_cmd_search)

    l = sub.add_parser("list", help="list stored papers")
    l.add_argument("--profile", default=None)
    l.add_argument("--status", default=None,
                   choices=["unrated", "keep", "maybe", "reject"])
    l.add_argument("--min-score", type=int, default=None,
                   help="only show papers with relevance score >= N (0-4)")
    l.set_defaults(func=_cmd_list)

    t = sub.add_parser("tag", help="set relevance for a paper")
    t.add_argument("id", type=int)
    t.add_argument("relevance", choices=["keep", "maybe", "reject", "unrated"])
    t.add_argument("--note", default=None)
    t.set_defaults(func=_cmd_tag)

    n = sub.add_parser("note", help="attach a note to a paper")
    n.add_argument("id", type=int)
    n.add_argument("text")
    n.set_defaults(func=_cmd_note)

    e = sub.add_parser("export", help="export papers to output/")
    e.add_argument("--profile", default=None)
    e.add_argument("--format", default="md", choices=["md", "csv"])
    e.add_argument("--status", default=None,
                   choices=["unrated", "keep", "maybe", "reject"])
    e.add_argument("--min-score", type=int, default=None,
                   help="only export papers with relevance score >= N (0-4)")
    e.set_defaults(func=_cmd_export)

    ff = sub.add_parser("fetch-fulltext", help="fetch open-access full text")
    ff.add_argument("--profile", default=None)
    ff.add_argument("--min-score", type=int, default=None)
    ff.set_defaults(func=_cmd_fetch_fulltext)

    kb = sub.add_parser("build-kb", help="build the RAG knowledge base (JSONL)")
    kb.add_argument("--profile", default=None)
    kb.add_argument("--min-score", type=int, default=None)
    kb.set_defaults(func=_cmd_build_kb)

    an = sub.add_parser("analyze", help="auto-analyze new cases via Claude (needs API key)")
    an.add_argument("--profile", default=None)
    an.add_argument("--min-score", type=int, default=None)
    an.add_argument("--model", default=None, help="override the Claude model")
    an.add_argument("--limit", type=int, default=None, help="cap how many to analyze")
    an.set_defaults(func=_cmd_analyze)

    be = sub.add_parser("build-embeddings",
                        help="embed analyzed cases for RAG retrieval (needs Voyage key)")
    be.add_argument("--model", default=None, help="override the Voyage model")
    be.set_defaults(func=_cmd_build_embeddings)

    ic = sub.add_parser("import-csv", help="import article URLs from a CSV into the library")
    ic.add_argument("path", help="path to the CSV of URLs")
    ic.add_argument("--profile", default="case-studies")
    ic.set_defaults(func=_cmd_import_csv)

    ev = sub.add_parser("eval", help="run retrieval evaluation against a golden set")
    ev.add_argument("--golden", default=None,
                    help="path to golden set JSONL (default: eval/golden_set.jsonl)")
    ev.add_argument("--k", default=None,
                    help="comma-separated k values for P@k/R@k/Hit@k (default: 1,3,5)")
    ev.add_argument("--output", default=None,
                    help="write full JSON results to this path")
    ev.set_defaults(func=_cmd_eval)

    st = sub.add_parser("stats", help="show counts")
    st.set_defaults(func=_cmd_stats)
    return p


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)
    store = Store()
    try:
        return args.func(args, store)
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
