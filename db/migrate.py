"""One-time, idempotent migration of the two legacy SQLite databases
(content/content_history.db, image/alnafi_posts.db) into the merged
data/alnafi_pipeline.db. Safe to re-run: each table is only populated if
still empty. Original files are backed up (never deleted) before copying.

IDs are reassigned by SQLite autoincrement rather than preserved from the
source databases (per project decision — nothing outside the app referenced
the old IDs), so generated_posts.generation_id is always NULL for migrated
image rows (there was no cross-referencing before this merge).
"""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .connection import get_connection, init_schema

ROOT = Path(__file__).parent.parent
CONTENT_DB = ROOT / "content" / "content_history.db"
IMAGE_DB = ROOT / "image" / "alnafi_posts.db"
BACKUP_DIR = ROOT / "backup"


def _backup(path: Path) -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"{path.stem}_{timestamp}{path.suffix}"
    shutil.copy2(path, dest)
    return dest


def _migrate_generations(target: sqlite3.Connection):
    existing = target.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    if not CONTENT_DB.exists():
        print("content/content_history.db not found — skipping (nothing to migrate)")
        return
    if existing > 0:
        print(f"generations already has {existing} row(s) — skipping to avoid duplicates")
        return

    backup_path = _backup(CONTENT_DB)
    print(f"Backed up content_history.db -> {backup_path}")

    src = sqlite3.connect(CONTENT_DB)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM generations").fetchall()
    for r in rows:
        target.execute("""
            INSERT INTO generations (
                created_at, topic, platform, page_promoted, content_type,
                audience, tone, keywords, social_meta, research_brief,
                writer_system, writer_human, final_content, filepath
            ) VALUES (:created_at, :topic, :platform, :page_promoted, :content_type,
                :audience, :tone, :keywords, :social_meta, :research_brief,
                :writer_system, :writer_human, :final_content, :filepath)
        """, dict(r))
    target.commit()
    src.close()
    print(f"Migrated {len(rows)} row(s) from content/content_history.db")


def _migrate_generated_posts(target: sqlite3.Connection):
    existing = target.execute("SELECT COUNT(*) FROM generated_posts").fetchone()[0]
    if not IMAGE_DB.exists():
        print("image/alnafi_posts.db not found — skipping (nothing to migrate)")
        return
    if existing > 0:
        print(f"generated_posts already has {existing} row(s) — skipping to avoid duplicates")
        return

    backup_path = _backup(IMAGE_DB)
    print(f"Backed up alnafi_posts.db -> {backup_path}")

    src = sqlite3.connect(IMAGE_DB)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM generated_posts").fetchall()
    for r in rows:
        target.execute("""
            INSERT INTO generated_posts (
                timestamp, sector, post_type, canvas_size, provider, quality,
                headline, platforms, image_prompt, system_prompt, image_data, generation_id
            ) VALUES (:timestamp, :sector, :post_type, :canvas_size, :provider, :quality,
                :headline, :platforms, :image_prompt, :system_prompt, :image_data, NULL)
        """, dict(r))
    target.commit()
    src.close()
    print(f"Migrated {len(rows)} row(s) from image/alnafi_posts.db")


def migrate():
    init_schema()
    target = get_connection()
    _migrate_generations(target)
    _migrate_generated_posts(target)
    target.close()


if __name__ == "__main__":
    migrate()
