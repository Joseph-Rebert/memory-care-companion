"""SQLite storage: papers + review status + tags.

Dedup happens at insert time via the ``dedup_key`` unique index, so re-running
a search updates existing rows instead of creating duplicates.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from .normalize import Paper
from .relevance import score_paper

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "papers.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key  TEXT UNIQUE NOT NULL,
    source     TEXT, source_id TEXT,
    doi        TEXT, title TEXT, abstract TEXT, authors TEXT,
    year       INTEGER, venue TEXT, url TEXT, pdf_url TEXT,
    pub_types  TEXT, profile TEXT,
    score      INTEGER DEFAULT 0,
    matched    TEXT DEFAULT '',
    pmcid      TEXT DEFAULT '',
    oa_status  TEXT DEFAULT '',
    full_text  TEXT DEFAULT '',
    text_source TEXT DEFAULT 'abstract',
    fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS review (
    paper_id   INTEGER PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    relevance  TEXT DEFAULT 'unrated',   -- unrated | keep | maybe | reject
    notes      TEXT DEFAULT '',
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS tags (
    paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    tag      TEXT,
    PRIMARY KEY (paper_id, tag)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str = DEFAULT_DB):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after a DB was first created."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(papers)")}
        additions = {
            "score": "INTEGER DEFAULT 0",
            "matched": "TEXT DEFAULT ''",
            "pmcid": "TEXT DEFAULT ''",
            "oa_status": "TEXT DEFAULT ''",
            "full_text": "TEXT DEFAULT ''",
            "text_source": "TEXT DEFAULT 'abstract'",
        }
        for name, decl in additions.items():
            if name not in cols:
                self.conn.execute(f"ALTER TABLE papers ADD COLUMN {name} {decl}")

    def upsert(self, paper: Paper) -> tuple[int, bool]:
        """Insert a paper or update the existing one. Returns (id, is_new)."""
        key = paper.dedup_key()
        score, matched = score_paper(paper)
        cur = self.conn.execute("SELECT id FROM papers WHERE dedup_key = ?", (key,))
        existing = cur.fetchone()
        if existing:
            pid = existing["id"]
            # Only fill in fields that are now non-empty (don't clobber good data),
            # and recompute the relevance score from the merged abstract.
            self.conn.execute(
                """UPDATE papers SET
                     abstract  = CASE WHEN ?<>'' THEN ? ELSE abstract END,
                     pdf_url   = CASE WHEN ?<>'' THEN ? ELSE pdf_url END,
                     doi       = CASE WHEN ?<>'' THEN ? ELSE doi END,
                     pmcid     = CASE WHEN ?<>'' THEN ? ELSE pmcid END,
                     oa_status = CASE WHEN ?<>'' THEN ? ELSE oa_status END,
                     score     = ?, matched = ?
                   WHERE id = ?""",
                (paper.abstract, paper.abstract, paper.pdf_url, paper.pdf_url,
                 paper.doi, paper.doi, paper.pmcid, paper.pmcid,
                 paper.oa_status, paper.oa_status, score, matched, pid),
            )
            self.conn.commit()
            return pid, False

        cur = self.conn.execute(
            """INSERT INTO papers
                 (dedup_key, source, source_id, doi, title, abstract, authors,
                  year, venue, url, pdf_url, pub_types, profile, score, matched,
                  pmcid, oa_status, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (key, paper.source, paper.source_id, paper.doi, paper.title,
             paper.abstract, paper.authors, paper.year, paper.venue, paper.url,
             paper.pdf_url, paper.pub_types, paper.profile, score, matched,
             paper.pmcid, paper.oa_status, _now()),
        )
        pid = cur.lastrowid
        self.conn.execute(
            "INSERT INTO review (paper_id, relevance, updated_at) VALUES (?, 'unrated', ?)",
            (pid, _now()),
        )
        self.conn.commit()
        return pid, True

    def set_relevance(self, paper_id: int, relevance: str, note: str | None = None) -> bool:
        if relevance not in ("unrated", "keep", "maybe", "reject"):
            raise ValueError(f"invalid relevance: {relevance}")
        cur = self.conn.execute("SELECT 1 FROM papers WHERE id = ?", (paper_id,))
        if not cur.fetchone():
            return False
        if note is not None:
            self.conn.execute(
                "UPDATE review SET relevance=?, notes=?, updated_at=? WHERE paper_id=?",
                (relevance, note, _now(), paper_id),
            )
        else:
            self.conn.execute(
                "UPDATE review SET relevance=?, updated_at=? WHERE paper_id=?",
                (relevance, _now(), paper_id),
            )
        self.conn.commit()
        return True

    def set_fulltext(self, paper_id: int, text: str, source: str) -> None:
        self.conn.execute(
            "UPDATE papers SET full_text = ?, text_source = ? WHERE id = ?",
            (text, source, paper_id),
        )
        self.conn.commit()

    def add_tag(self, paper_id: int, tag: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO tags (paper_id, tag) VALUES (?, ?)", (paper_id, tag)
        )
        self.conn.commit()

    def list_papers(self, profile: str | None = None, status: str | None = None,
                    min_score: int | None = None) -> list[sqlite3.Row]:
        sql = (
            "SELECT p.*, r.relevance, r.notes FROM papers p "
            "JOIN review r ON r.paper_id = p.id WHERE 1=1"
        )
        args: list = []
        if profile:
            sql += " AND p.profile = ?"; args.append(profile)
        if status:
            sql += " AND r.relevance = ?"; args.append(status)
        if min_score is not None:
            sql += " AND p.score >= ?"; args.append(min_score)
        # Highest relevance first, then newest.
        sql += " ORDER BY p.score DESC, p.year DESC, p.id DESC"
        return self.conn.execute(sql, args).fetchall()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]

    def close(self) -> None:
        self.conn.close()
