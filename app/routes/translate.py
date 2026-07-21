import io
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTasks

from app.auth import CurrentUser, get_current_user
from app.db import repo_translation
from app.db.base import get_session_factory
from app.deps import DbDep, StorageDep
from app.sse import sse_stream
from app.storage import get_storage_backend
from app.storage.base import StorageBackend
from app.templating import render
from imagegen import config as igcfg
from imagegen.credentials import resolve_api_key
from imagegen.providers import generate_translation_image

router = APIRouter(prefix="/translate", tags=["translate"])

MAX_IMAGES_PER_BATCH = 100
MAX_WORKERS = 20


@router.get("")
def translate_form(request: Request, user: CurrentUser = Depends(get_current_user)):
    return render(
        request, "translate.html", user=user,
        sectors=igcfg.ALNAFI_SECTORS, providers={k: v for k, v in igcfg.PROVIDERS.items() if v != "prompt-only"},
        languages=igcfg.TRANSLATION_LANGUAGES, canvas_presets=igcfg.CANVAS_PRESETS,
    )


def _translate_one(job_id: uuid.UUID, image_bytes: bytes, target_language: str, *,
                    api_key: str, provider_id: str, quality_tier: str, canvas_size: str,
                    sector_info: dict, colors: dict, batch_id: uuid.UUID, storage: StorageBackend) -> None:
    db = get_session_factory()()
    try:
        start = time.time()
        result_bytes, usage, error = generate_translation_image(
            api_key, io.BytesIO(image_bytes), target_language, provider_id, quality_tier, canvas_size,
            sector_info, colors,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        if error or not result_bytes:
            repo_translation.mark_job_error(db, job_id, error_message=error or "No image returned", elapsed_ms=elapsed_ms)
            return
        output_key = storage.save(f"images/translations/{batch_id}/{job_id}.png", result_bytes, content_type="image/png")
        repo_translation.mark_job_done(db, job_id, output_storage_key=output_key, usage_json=usage, elapsed_ms=elapsed_ms)
    except Exception as e:
        repo_translation.mark_job_error(db, job_id, error_message=str(e))
    finally:
        db.close()


def _run_translation_batch(jobs_payload: list[dict], *, api_key: str, provider_id: str, quality_tier: str,
                            canvas_size: str, sector_info: dict, colors: dict, batch_id: uuid.UUID) -> None:
    """Runs off the request thread via BackgroundTasks. Fans out to a
    ThreadPoolExecutor (20 workers, matching the original Streamlit batch
    translate flow) — each worker opens its own DB session."""
    storage = get_storage_backend()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [
            pool.submit(
                _translate_one, job["job_id"], job["image_bytes"], job["target_language"],
                api_key=api_key, provider_id=provider_id, quality_tier=quality_tier, canvas_size=canvas_size,
                sector_info=sector_info, colors=colors, batch_id=batch_id, storage=storage,
            )
            for job in jobs_payload
        ]
        for f in futures:
            f.result()  # propagate nothing — errors are already recorded per-job


@router.post("/batch")
async def submit_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbDep,
    user: CurrentUser = Depends(get_current_user),
    provider_label: str = Form(...),
    quality_tier: str = Form("medium"),
    canvas_size: str = Form("1080x1080"),
    sector: str = Form(...),
    target_languages: list[str] = Form(...),
    images: list[UploadFile] = File(...),
):
    if len(images) == 0:
        raise HTTPException(status_code=400, detail="Upload at least one image")
    if len(images) > MAX_IMAGES_PER_BATCH:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_IMAGES_PER_BATCH} images per batch")
    if not target_languages:
        raise HTTPException(status_code=400, detail="Select at least one target language")

    provider_id = igcfg.PROVIDERS[provider_label]
    api_key, _source = resolve_api_key(provider_id)
    sector_info = igcfg.ALNAFI_SECTORS[sector]
    colors = {"primary": sector_info["color_primary"], "secondary": sector_info["color_secondary"],
              "accent": sector_info["color_accent"]}

    total_jobs = len(images) * len(target_languages)
    batch = repo_translation.create_batch(db, created_by_user_id=user.id, total_jobs=total_jobs)

    storage = get_storage_backend()
    jobs_payload = []
    for img in images:
        content = await img.read()
        storage.save(f"images/translations/{batch.id}/source_{img.filename}", content, content_type=img.content_type or "image/png")
        for lang in target_languages:
            job = repo_translation.create_job(
                db, batch_id=batch.id, created_by_user_id=user.id, source_filename=img.filename,
                source_image_storage_key=f"images/translations/{batch.id}/source_{img.filename}",
                target_language=lang, provider=provider_label, quality=quality_tier, canvas_size=canvas_size,
            )
            jobs_payload.append({"job_id": job.id, "image_bytes": content, "target_language": lang})

    background_tasks.add_task(
        _run_translation_batch, jobs_payload, api_key=api_key, provider_id=provider_id,
        quality_tier=quality_tier, canvas_size=canvas_size, sector_info=sector_info, colors=colors,
        batch_id=batch.id,
    )

    return render(request, "partials/_progress_sse.html", user=user, job_id=batch.id, stream_url=f"/translate/batch/{batch.id}/stream")


def _poll_batch(batch_id: uuid.UUID) -> dict:
    db = get_session_factory()()
    try:
        batch = repo_translation.get_batch(db, batch_id)
        if batch is None:
            return {"event": "error", "error": "batch not found", "terminal": True}
        if batch.status == "done":
            return {"event": "complete", "completed": batch.completed_jobs, "total": batch.total_jobs,
                    "redirect": f"/translate/batch/{batch_id}", "terminal": True}
        return {"event": "stage", "completed": batch.completed_jobs, "total": batch.total_jobs, "terminal": False}
    finally:
        db.close()


@router.get("/batch/{batch_id}/stream")
async def stream_batch(batch_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)):
    return StreamingResponse(sse_stream(lambda: _poll_batch(batch_id)), media_type="text/event-stream")


@router.get("/batch/{batch_id}")
def batch_results(request: Request, batch_id: uuid.UUID, db: DbDep, storage: StorageDep, user: CurrentUser = Depends(get_current_user)):
    batch = repo_translation.get_batch(db, batch_id)
    jobs = repo_translation.list_jobs_for_batch(db, batch_id)
    for job in jobs:
        job.image_url = storage.get_url(job.output_storage_key) if job.output_storage_key else None
    return render(request, "translate_batch.html", user=user, batch=batch, jobs=jobs)


@router.get("/batch/{batch_id}/zip")
def batch_zip(batch_id: uuid.UUID, db: DbDep, storage: StorageDep, user: CurrentUser = Depends(get_current_user)):
    jobs = repo_translation.list_jobs_for_batch(db, batch_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for job in jobs:
            if job.status == "success" and job.output_storage_key:
                base = (job.source_filename or f"job-{job.id}").rsplit(".", 1)[0]
                lang_safe = job.target_language.replace(" ", "_").replace("/", "-")
                zf.writestr(f"{base}_{lang_safe}.png", storage.get(job.output_storage_key))
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=translations_{batch_id}.zip"},
    )
