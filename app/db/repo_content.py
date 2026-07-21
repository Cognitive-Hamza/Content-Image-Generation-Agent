from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Generation


def save_generation(
    db: Session,
    *,
    created_by_user_id: int | None,
    topic: str,
    platform: str | None = None,
    page_promoted: str | None = None,
    content_type: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
    keywords: str | None = None,
    research_brief: str | None = None,
    writer_system: str | None = None,
    writer_human: str | None = None,
    final_content: str | None = None,
    output_storage_key: str | None = None,
    social_meta: dict | None = None,
) -> Generation:
    generation = Generation(
        created_by_user_id=created_by_user_id,
        topic=topic,
        platform=platform,
        page_promoted=page_promoted,
        content_type=content_type,
        audience=audience,
        tone=tone,
        keywords=keywords,
        research_brief=research_brief,
        writer_system=writer_system,
        writer_human=writer_human,
        final_content=final_content,
        output_storage_key=output_storage_key,
        social_meta=social_meta,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


def search_generations(
    db: Session,
    *,
    topic: str | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    limit: int = 10,
) -> list[Generation]:
    stmt = select(Generation).order_by(Generation.created_at.desc()).limit(limit)
    if topic:
        stmt = stmt.where(Generation.topic.ilike(f"%{topic}%"))
    if platform:
        stmt = stmt.where(Generation.platform == platform)
    if content_type:
        stmt = stmt.where(Generation.content_type == content_type)
    return list(db.execute(stmt).scalars())


def get_generation(db: Session, generation_id: int) -> Generation | None:
    return db.get(Generation, generation_id)


def list_recent(db: Session, limit: int = 15) -> list[Generation]:
    stmt = select(Generation).order_by(Generation.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())
