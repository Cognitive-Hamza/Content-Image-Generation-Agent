import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("ALNAFI_DB_PATH", Path(__file__).parent.parent / "data" / "alnafi_pipeline.db"))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at          TEXT    NOT NULL,
                topic               TEXT    NOT NULL,
                platform            TEXT,
                page_promoted       TEXT,
                content_type        TEXT,
                audience            TEXT,
                tone                TEXT,
                keywords            TEXT,
                social_meta         TEXT,
                research_brief      TEXT,
                writer_system       TEXT,
                writer_human        TEXT,
                final_content       TEXT,
                filepath            TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp      TEXT    NOT NULL,
                sector         TEXT,
                post_type      TEXT,
                canvas_size    TEXT,
                provider       TEXT,
                quality        TEXT,
                headline       TEXT,
                platforms      TEXT,
                image_prompt   TEXT,
                system_prompt  TEXT,
                image_data     BLOB    NOT NULL,
                generation_id  INTEGER REFERENCES generations(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_generated_posts_generation_id
            ON generated_posts(generation_id)
        """)
