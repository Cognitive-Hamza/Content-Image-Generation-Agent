import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import TranslationBatch, TranslationJob


def create_batch(db: Session, *, created_by_user_id: int | None, total_jobs: int) -> TranslationBatch:
    batch = TranslationBatch(
        created_by_user_id=created_by_user_id, total_jobs=total_jobs, completed_jobs=0, status="running"
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def create_job(
    db: Session,
    *,
    batch_id: uuid.UUID,
    created_by_user_id: int | None,
    source_filename: str | None,
    source_image_storage_key: str | None,
    target_language: str,
    provider: str | None,
    quality: str | None,
    canvas_size: str | None,
) -> TranslationJob:
    job = TranslationJob(
        batch_id=batch_id,
        created_by_user_id=created_by_user_id,
        source_filename=source_filename,
        source_image_storage_key=source_image_storage_key,
        target_language=target_language,
        provider=provider,
        quality=quality,
        canvas_size=canvas_size,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _increment_batch_completed(db: Session, batch_id: uuid.UUID) -> None:
    # Atomic SQL-level increment — safe against the 20 concurrent worker
    # threads translation batches run under (see imagegen.providers).
    db.execute(
        update(TranslationBatch)
        .where(TranslationBatch.id == batch_id)
        .values(completed_jobs=TranslationBatch.completed_jobs + 1)
    )
    db.commit()
    batch = db.get(TranslationBatch, batch_id)
    if batch is not None and batch.completed_jobs >= batch.total_jobs and batch.status != "done":
        batch.status = "done"
        db.commit()


def mark_job_done(
    db: Session, job_id: int, *, output_storage_key: str, usage_json: dict | None = None, elapsed_ms: int | None = None
) -> TranslationJob:
    job = db.get(TranslationJob, job_id)
    job.status = "success"
    job.output_storage_key = output_storage_key
    job.usage_json = usage_json
    job.elapsed_ms = elapsed_ms
    db.commit()
    _increment_batch_completed(db, job.batch_id)
    db.refresh(job)
    return job


def mark_job_error(db: Session, job_id: int, *, error_message: str, elapsed_ms: int | None = None) -> TranslationJob:
    job = db.get(TranslationJob, job_id)
    job.status = "error"
    job.error_message = error_message
    job.elapsed_ms = elapsed_ms
    db.commit()
    _increment_batch_completed(db, job.batch_id)
    db.refresh(job)
    return job


def get_batch(db: Session, batch_id: uuid.UUID) -> TranslationBatch | None:
    return db.get(TranslationBatch, batch_id)


def list_jobs_for_batch(db: Session, batch_id: uuid.UUID) -> list[TranslationJob]:
    stmt = select(TranslationJob).where(TranslationJob.batch_id == batch_id).order_by(TranslationJob.id)
    return list(db.execute(stmt).scalars())
