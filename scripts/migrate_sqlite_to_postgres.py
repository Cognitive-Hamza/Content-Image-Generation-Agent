"""One-off, idempotent migration: copies real data from the legacy SQLite DB
(data/alnafi_pipeline.db) into the new Postgres schema (`cig`) + storage backend.

Never deletes or modifies the source SQLite file. Safe to re-run: if
cig.generations or cig.generated_posts already has rows, the script refuses
to run again rather than risk duplicating data (mirrors the guard pattern the
old db/migrate.py used before it was retired in Phase 1).

Usage:
    python -m scripts.migrate_sqlite_to_postgres
"""
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db.base import get_session_factory
from app.db.models import GeneratedPost, Generation, User
from app.storage import get_storage_backend


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value)
    # Source timestamps were written via datetime.now().isoformat() — naive,
    # server-local. Best-effort: treat as UTC rather than guess a local zone.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _get_or_create_migration_user(db, email: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name="SQLite migration", created_at=datetime.now(timezone.utc))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def migrate() -> None:
    settings = get_settings()
    sqlite_path = Path(settings.ALNAFI_DB_PATH)
    if not sqlite_path.exists():
        print(f"No SQLite DB found at {sqlite_path} — nothing to migrate.")
        return

    db = get_session_factory()()
    storage = get_storage_backend()

    try:
        already_migrated = (
            db.execute(select(Generation.id).limit(1)).first() is not None
            or db.execute(select(GeneratedPost.id).limit(1)).first() is not None
        )
        if already_migrated:
            print(
                "cig.generations / cig.generated_posts already have rows — refusing to "
                "re-run (idempotency guard). Truncate those tables manually first if you "
                "really want to re-migrate."
            )
            return

        migration_user = _get_or_create_migration_user(db, settings.MIGRATION_FALLBACK_USER_EMAIL)

        conn = sqlite3.connect(str(sqlite_path))
        conn.row_factory = sqlite3.Row

        # ── generations ──────────────────────────────────────────────────
        gen_id_map: dict[int, int] = {}  # old sqlite id -> new postgres id
        gen_rows = conn.execute("SELECT * FROM generations ORDER BY id").fetchall()
        for row in gen_rows:
            generation = Generation(
                created_at=_parse_timestamp(row["created_at"]),
                created_by_user_id=migration_user.id,
                topic=row["topic"],
                platform=row["platform"],
                page_promoted=row["page_promoted"],
                content_type=row["content_type"],
                audience=row["audience"],
                tone=row["tone"],
                keywords=row["keywords"],
                research_brief=row["research_brief"],
                writer_system=row["writer_system"],
                writer_human=row["writer_human"],
                final_content=row["final_content"],
                social_meta=json.loads(row["social_meta"]) if row["social_meta"] else None,
            )
            db.add(generation)
            db.flush()  # assigns generation.id without committing
            gen_id_map[row["id"]] = generation.id
        db.commit()
        print(f"Migrated {len(gen_rows)} generations.")

        # ── generated_posts (images, incl. real BLOBs -> storage backend) ──
        post_rows = conn.execute("SELECT * FROM generated_posts ORDER BY id").fetchall()
        migrated_posts, failed_posts = 0, 0
        for row in post_rows:
            image_bytes = row["image_data"]
            try:
                storage_key = storage.save(
                    f"images/generated_posts/{uuid.uuid4()}.png", image_bytes, content_type="image/png"
                )
            except Exception as e:
                print(f"  FAILED to migrate post id={row['id']}: {e}", file=sys.stderr)
                failed_posts += 1
                continue

            old_generation_id = row["generation_id"]
            new_generation_id = gen_id_map.get(old_generation_id) if old_generation_id else None

            post = GeneratedPost(
                created_at=_parse_timestamp(row["timestamp"]),
                created_by_user_id=migration_user.id,
                sector=row["sector"],
                post_type=row["post_type"],
                canvas_size=row["canvas_size"],
                provider=row["provider"],
                quality=row["quality"],
                headline=row["headline"],
                platforms=json.loads(row["platforms"]) if row["platforms"] else None,
                image_prompt=row["image_prompt"],
                system_prompt=row["system_prompt"],
                storage_key=storage_key,
                byte_size=len(image_bytes) if image_bytes else 0,
                content_type="image/png",
                generation_id=new_generation_id,
            )
            db.add(post)
            migrated_posts += 1
        db.commit()
        conn.close()

        print(f"Migrated {migrated_posts} generated_posts ({failed_posts} failed).")
        print(f"Source SQLite DB left untouched at {sqlite_path}.")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
