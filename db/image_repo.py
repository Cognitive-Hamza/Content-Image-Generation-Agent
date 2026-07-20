import json
from datetime import datetime

from .connection import get_connection, init_schema

init_schema()


def save_post_to_db(image_bytes, image_prompt, system_prompt, meta):
    conn = get_connection()
    conn.execute("""
        INSERT INTO generated_posts
            (timestamp, sector, post_type, canvas_size, provider, quality,
             headline, platforms, image_prompt, system_prompt, image_data, generation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        meta.get("timestamp", datetime.now().isoformat()),
        meta.get("sector", ""),
        meta.get("post_type", ""),
        meta.get("canvas_size", ""),
        meta.get("provider", ""),
        meta.get("quality", ""),
        meta.get("headline", ""),
        json.dumps(meta.get("platforms", [])),
        image_prompt,
        system_prompt,
        image_bytes,
        meta.get("generation_id"),
    ))
    conn.commit()
    conn.close()


def load_all_posts(limit=200):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM generated_posts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_post_from_db(post_id):
    conn = get_connection()
    conn.execute("DELETE FROM generated_posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
