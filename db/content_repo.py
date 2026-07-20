import json
from datetime import datetime

from .connection import get_connection, init_schema

init_schema()


def save_generation(
    topic, platform, page_promoted, content_type,
    audience, tone, keywords,
    research_brief, writer_system, writer_human,
    final_content, filepath,
    social_meta=None,
):
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO generations (
            created_at, topic, platform, page_promoted, content_type,
            audience, tone, keywords, social_meta,
            research_brief, writer_system, writer_human,
            final_content, filepath
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.now().isoformat(timespec="seconds"),
        topic, platform, page_promoted, content_type,
        audience, tone, keywords,
        json.dumps(social_meta) if social_meta else None,
        research_brief, writer_system, writer_human,
        final_content, filepath,
    ))
    con.commit()
    row_id = cur.lastrowid
    con.close()
    return row_id


def search_generations(topic=None, platform=None, content_type=None, limit=10):
    parts, params = [], []
    if topic:
        parts.append("topic LIKE ?")
        params.append(f"%{topic}%")
    if platform:
        parts.append("platform = ?")
        params.append(platform)
    if content_type:
        parts.append("content_type = ?")
        params.append(content_type)
    where = ("WHERE " + " AND ".join(parts)) if parts else ""
    with get_connection() as c:
        return c.execute(
            f"SELECT id, created_at, topic, platform, content_type, filepath "
            f"FROM generations {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()


def get_generation(row_id):
    with get_connection() as c:
        return c.execute(
            "SELECT * FROM generations WHERE id = ?", (row_id,)
        ).fetchone()


def list_recent(limit=15):
    with get_connection() as c:
        return c.execute(
            "SELECT id, created_at, topic, platform, content_type, page_promoted "
            "FROM generations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
