from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GeneratedPost
from app.storage.base import StorageBackend


def save_post_to_db(
    db: Session,
    *,
    storage_key: str,
    byte_size: int,
    image_prompt: str | None,
    system_prompt: str | None,
    meta: dict,
    content_type: str = "image/png",
) -> GeneratedPost:
    post = GeneratedPost(
        created_by_user_id=meta.get("created_by_user_id"),
        sector=meta.get("sector", ""),
        post_type=meta.get("post_type", ""),
        canvas_size=meta.get("canvas_size", ""),
        provider=meta.get("provider", ""),
        quality=meta.get("quality", ""),
        headline=meta.get("headline", ""),
        platforms=meta.get("platforms", []),
        image_prompt=image_prompt,
        system_prompt=system_prompt,
        storage_key=storage_key,
        byte_size=byte_size,
        content_type=content_type,
        generation_id=meta.get("generation_id"),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def load_all_posts(db: Session, limit: int = 200) -> list[GeneratedPost]:
    stmt = select(GeneratedPost).order_by(GeneratedPost.id.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def delete_post_from_db(db: Session, storage: StorageBackend, post_id: int) -> None:
    post = db.get(GeneratedPost, post_id)
    if post is None:
        return
    db.delete(post)
    db.commit()
    try:
        storage.delete(post.storage_key)
    except Exception:
        pass  # the DB row is the source of truth; storage cleanup is best-effort
