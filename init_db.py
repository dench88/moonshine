"""Run once to create the SQLite schema."""
import sqlite3
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'running',
    cycle_count INTEGER NOT NULL DEFAULT 0,
    max_cycles  INTEGER NOT NULL DEFAULT 40,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES runs(id),
    cycle_number        INTEGER NOT NULL,
    url                 TEXT    NOT NULL,
    title               TEXT,
    source_name         TEXT,
    author              TEXT,
    publish_date        TEXT,
    extracted_text      TEXT,
    summary             TEXT,
    detailed_summary    TEXT,
    why_relevant        TEXT,
    key_points          TEXT,
    quality_score       INTEGER DEFAULT 0,
    relevance_score     INTEGER DEFAULT 0,
    status              TEXT    NOT NULL DEFAULT 'accepted',
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES runs(id),
    cycle_number        INTEGER NOT NULL,
    draft_markdown      TEXT,
    gaps_to_research    TEXT,
    next_search_angles  TEXT,
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS failures (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES runs(id),
    cycle_number  INTEGER NOT NULL,
    stage         TEXT,
    url           TEXT,
    error_message TEXT,
    created_at    TEXT    NOT NULL
);

-- FTS5 index over sources: search title, summary, key_points, extracted_text
CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
    title,
    summary,
    key_points,
    extracted_text,
    content=sources,
    content_rowid=id
);

-- FTS5 index over drafts: search the full draft markdown
CREATE VIRTUAL TABLE IF NOT EXISTS drafts_fts USING fts5(
    draft_markdown,
    content=drafts,
    content_rowid=id
);
"""

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Database initialised at {DB_PATH}")
