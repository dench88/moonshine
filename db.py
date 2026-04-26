import sqlite3
import contextlib
from config import DB_PATH

_migrated = False


def get_conn():
    global _migrated
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if not _migrated:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id        INTEGER NOT NULL REFERENCES runs(id),
                cycle         INTEGER NOT NULL,
                role          TEXT    NOT NULL,
                model         TEXT    NOT NULL,
                input_tokens  INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        _migrated = True
    return conn


@contextlib.contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def create_run(topic: str, max_cycles: int) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO runs (topic, status, cycle_count, max_cycles, created_at, updated_at)
               VALUES (?, 'running', 0, ?, datetime('now'), datetime('now'))""",
            (topic, max_cycles),
        )
        return cur.lastrowid


def get_run(run_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_latest_run() -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_run_status(run_id: int, status: str, cycle_count: int | None = None):
    conn = get_conn()
    try:
        if cycle_count is not None:
            conn.execute(
                "UPDATE runs SET status=?, cycle_count=?, updated_at=datetime('now') WHERE id=?",
                (status, cycle_count, run_id),
            )
        else:
            conn.execute(
                "UPDATE runs SET status=?, updated_at=datetime('now') WHERE id=?",
                (status, run_id),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def save_source(run_id: int, cycle: int, data: dict) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO sources
               (run_id, cycle_number, url, title, source_name, author,
                publish_date, extracted_text, summary, detailed_summary,
                why_relevant, key_points, quality_score, relevance_score,
                status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (
                run_id, cycle,
                data.get("url", ""),
                data.get("title", ""),
                data.get("source_name", ""),
                data.get("author", ""),
                data.get("publish_date", ""),
                data.get("extracted_text", ""),
                data.get("summary", ""),
                data.get("detailed_summary", ""),
                data.get("why_relevant", ""),
                data.get("key_points", ""),
                data.get("quality_score", 0),
                data.get("relevance_score", 0),
                data.get("status", "accepted"),
            ),
        )
        source_id = cur.lastrowid
        conn.execute(
            "INSERT INTO sources_fts(rowid, title, summary, key_points, extracted_text) VALUES (?, ?, ?, ?, ?)",
            (source_id, data.get("title", ""), data.get("summary", ""),
             data.get("key_points", ""), data.get("extracted_text", "")),
        )
        return source_id


def get_accepted_urls(run_id: int) -> set[str]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT url FROM sources WHERE run_id=? AND status='accepted'",
            (run_id,),
        ).fetchall()
        return {r["url"] for r in rows}
    finally:
        conn.close()


def get_all_summaries(run_id: int) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT cycle_number, url, title, summary, why_relevant, key_points,
                      quality_score, relevance_score
               FROM sources WHERE run_id=? AND status='accepted'
               ORDER BY cycle_number, id""",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

def save_draft(run_id: int, cycle: int, draft_md: str, gaps: str, next_angles: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO drafts
               (run_id, cycle_number, draft_markdown, gaps_to_research, next_search_angles,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (run_id, cycle, draft_md, gaps, next_angles),
        )
        draft_id = cur.lastrowid
        conn.execute(
            "INSERT INTO drafts_fts(rowid, draft_markdown) VALUES (?, ?)",
            (draft_id, draft_md),
        )
        return draft_id


def get_latest_draft(run_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM drafts WHERE run_id=? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------

def log_token_usage(run_id: int, cycle: int, role: str, model: str,
                    input_tokens: int, output_tokens: int):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO token_usage (run_id, cycle, role, model, input_tokens, output_tokens)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, cycle, role, model, input_tokens, output_tokens),
        )
        conn.commit()
    finally:
        conn.close()


def get_token_usage_summary(run_id: int) -> list[dict]:
    """Return total input/output tokens grouped by role and model for a run."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT role, model,
                      SUM(input_tokens)  AS input_tokens,
                      SUM(output_tokens) AS output_tokens
               FROM token_usage
               WHERE run_id = ?
               GROUP BY role, model
               ORDER BY role""",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_failure(run_id: int, cycle: int, stage: str, url: str, error: str):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO failures (run_id, cycle_number, stage, url, error_message, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (run_id, cycle, stage, url, error),
        )
        conn.commit()
    finally:
        conn.close()
