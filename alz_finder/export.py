"""Export stored papers to a readable Markdown or CSV file in output/."""
from __future__ import annotations

import csv
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_DIR = os.path.join(ROOT, "output")


def export_markdown(rows, profile: str | None, datestamp: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    suffix = f"_{profile}" if profile else ""
    path = os.path.join(OUT_DIR, f"results{suffix}_{datestamp}.md")
    with open(path, "w") as fh:
        title = f"Results{' — ' + profile if profile else ''} ({datestamp})"
        fh.write(f"# {title}\n\n{len(rows)} papers.\n\n")
        for r in rows:
            fh.write(f"## {r['title'] or '(untitled)'}\n\n")
            meta = [x for x in (r["authors"], str(r["year"] or ""), r["venue"]) if x]
            if meta:
                fh.write(f"*{' · '.join(meta)}*\n\n")
            badges = [f"source: {r['source']}", f"relevance: {r['relevance']}"]
            if r["pub_types"]:
                badges.append(r["pub_types"])
            fh.write("`" + "` `".join(badges) + "`\n\n")
            if r["abstract"]:
                abs = r["abstract"]
                fh.write((abs[:600] + "…" if len(abs) > 600 else abs) + "\n\n")
            links = []
            if r["url"]:
                links.append(f"[link]({r['url']})")
            if r["pdf_url"]:
                links.append(f"[pdf]({r['pdf_url']})")
            if r["doi"]:
                links.append(f"[doi](https://doi.org/{r['doi']})")
            if links:
                fh.write(" · ".join(links) + "\n\n")
            if r["notes"]:
                fh.write(f"> {r['notes']}\n\n")
            fh.write("---\n\n")
    return path


def export_csv(rows, profile: str | None, datestamp: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    suffix = f"_{profile}" if profile else ""
    path = os.path.join(OUT_DIR, f"results{suffix}_{datestamp}.csv")
    cols = ["id", "title", "authors", "year", "venue", "source", "doi",
            "url", "pdf_url", "pub_types", "relevance", "notes"]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r[c] for c in cols])
    return path
