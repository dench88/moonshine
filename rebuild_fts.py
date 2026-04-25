"""Rebuild FTS5 indexes from existing data. Safe to run multiple times."""
import sqlite3
from config import DB_PATH


def rebuild(conn: sqlite3.Connection):
    conn.execute("DELETE FROM sources_fts")
    conn.execute(
        """INSERT INTO sources_fts(rowid, title, summary, key_points, extracted_text)
           SELECT id, title, summary, key_points, extracted_text FROM sources"""
    )
    source_count = conn.execute("SELECT COUNT(*) FROM sources_fts").fetchone()[0]

    conn.execute("DELETE FROM drafts_fts")
    conn.execute(
        """INSERT INTO drafts_fts(rowid, draft_markdown)
           SELECT id, draft_markdown FROM drafts"""
    )
    draft_count = conn.execute("SELECT COUNT(*) FROM drafts_fts").fetchone()[0]

    conn.commit()
    print(f"Indexed {source_count} sources and {draft_count} drafts.")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    rebuild(conn)
    conn.close()
