import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column()


class Generation(Base):
    """Content-generation records — superset of the old SQLite `generations` table."""
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    topic: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(Text)
    page_promoted: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)
    social_meta: Mapped[dict | None] = mapped_column(JSONB)
    research_brief: Mapped[str | None] = mapped_column(Text)
    writer_system: Mapped[str | None] = mapped_column(Text)
    writer_human: Mapped[str | None] = mapped_column(Text)
    final_content: Mapped[str | None] = mapped_column(Text)
    output_storage_key: Mapped[str | None] = mapped_column(Text)

    posts: Mapped[list["GeneratedPost"]] = relationship(back_populates="generation")


class GeneratedPost(Base):
    """Generated marketing images — `storage_key` replaces the old raw BLOB column."""
    __tablename__ = "generated_posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    sector: Mapped[str | None] = mapped_column(Text)
    post_type: Mapped[str | None] = mapped_column(Text)
    canvas_size: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(Text)
    platforms: Mapped[dict | None] = mapped_column(JSONB)
    image_prompt: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)

    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100), default="image/png", nullable=False)

    generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL"), index=True
    )

    generation: Mapped["Generation | None"] = relationship(back_populates="posts")


class TranslationBatch(Base):
    """Groups N per-image-per-language translation jobs submitted together."""
    __tablename__ = "translation_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    total_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running | done

    jobs: Mapped[list["TranslationJob"]] = relationship(back_populates="batch")


class TranslationJob(Base):
    """A single image x language translation job. Net-new — not persisted in the old app."""
    __tablename__ = "translation_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("translation_batches.id", ondelete="CASCADE"), index=True
    )
    source_filename: Mapped[str | None] = mapped_column(Text)
    source_image_storage_key: Mapped[str | None] = mapped_column(Text)
    target_language: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[str | None] = mapped_column(Text)
    canvas_size: Mapped[str | None] = mapped_column(Text)
    output_storage_key: Mapped[str | None] = mapped_column(Text)  # null until success

    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)  # queued|success|error
    error_message: Mapped[str | None] = mapped_column(Text)
    usage_json: Mapped[dict | None] = mapped_column(JSONB)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)

    batch: Mapped["TranslationBatch"] = relationship(back_populates="jobs")


class GenerationJob(Base):
    """Backs SSE progress for content generation (research -> write -> refine)."""
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    job_type: Mapped[str] = mapped_column(String(30), nullable=False)  # long_form | social_captions
    status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False
    )  # queued|researching|writing|refining|done|error
    params_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_generation_id: Mapped[int | None] = mapped_column(ForeignKey("generations.id"))
    error_message: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """Append-only audit trail. Never write secrets into `metadata_json`."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # null for system actions

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(50))
    # attribute named metadata_json (not `metadata`) because SQLAlchemy's
    # DeclarativeBase reserves that name; the actual DB column is still `metadata`.
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
