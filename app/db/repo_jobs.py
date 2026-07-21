import uuid

from sqlalchemy.orm import Session

from app.db.models import GenerationJob


def create_generation_job(db: Session, *, created_by_user_id: int | None, job_type: str, params_json: dict) -> GenerationJob:
    job = GenerationJob(
        created_by_user_id=created_by_user_id, job_type=job_type, status="queued", params_json=params_json
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_status(
    db: Session,
    job_id: uuid.UUID,
    status: str,
    *,
    result_generation_id: int | None = None,
    error_message: str | None = None,
) -> None:
    job = db.get(GenerationJob, job_id)
    if job is None:
        return
    job.status = status
    if result_generation_id is not None:
        job.result_generation_id = result_generation_id
    if error_message is not None:
        job.error_message = error_message
    db.commit()


def get_generation_job(db: Session, job_id: uuid.UUID) -> GenerationJob | None:
    return db.get(GenerationJob, job_id)
