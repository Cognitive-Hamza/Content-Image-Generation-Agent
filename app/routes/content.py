import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTasks

from app.auth import CurrentUser, get_current_user
from app.db import repo_content, repo_jobs
from app.db.audit import log_action
from app.db.base import get_db, get_session_factory
from app.deps import DbDep
from app.sse import sse_stream
from app.storage import get_storage_backend
from app.templating import render
from pipeline import config as pcfg
from pipeline.page_finder import find_best_page
from pipeline.pipeline import generate_long_form_content, generate_social_captions

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/new")
def new_content_form(request: Request, user: CurrentUser = Depends(get_current_user)):
    return render(
        request,
        "content_new.html",
        user=user,
        platforms=pcfg.PLATFORMS,
        content_types=pcfg.CONTENT_TYPES,
        tones=pcfg.TONES,
        social_platforms=list(pcfg.SOCIAL_PLATFORM_RULES.keys()),
        social_post_types=pcfg.SOCIAL_POST_TYPES,
    )


@router.post("/pages/search")
def search_pages(
    request: Request,
    query: str = Form(...),
    platform_key: str = Form(...),
    user: CurrentUser = Depends(get_current_user),
):
    plat_name = pcfg.PLATFORMS.get(platform_key, (None,))[0]
    matches = find_best_page(query, platform=plat_name, top_n=5) if query.strip() else []
    return render(request, "partials/_page_search_results.html", user=user, matches=matches)


def _run_content_job(job_id: uuid.UUID, params: dict, created_by_user_id: int | None) -> None:
    """Runs off the request thread via BackgroundTasks. Opens its own DB
    session — the request's session is closed long before this finishes."""
    db = get_session_factory()()
    storage = get_storage_backend()
    try:
        repo_jobs.update_status(db, job_id, "researching")

        def on_stage(stage: str) -> None:
            repo_jobs.update_status(db, job_id, stage)

        try:
            if params["mode"] == "social_captions":
                result = generate_social_captions(
                    topic=params["topic"], keywords=params["keywords"], audience=params["audience"],
                    plat_name=params["plat_name"], plat_domain=params["plat_domain"],
                    alnafi_promo=params["page_promoted"], chosen_platforms=params["chosen_platforms"],
                    post_type=params["post_type"], caption_goal=params["caption_goal"], storage=storage,
                    db=db, created_by_user_id=created_by_user_id,
                )
            else:
                result = generate_long_form_content(
                    topic=params["topic"], keywords=params["keywords"], audience=params["audience"],
                    content_type=params["content_type"], word_count=params["word_count"], tone=params["tone"],
                    plat_name=params["plat_name"], plat_domain=params["plat_domain"],
                    alnafi_promo=params["page_promoted"], on_stage=on_stage, storage=storage,
                    db=db, created_by_user_id=created_by_user_id,
                )
            repo_jobs.update_status(db, job_id, "done", result_generation_id=result.db_id)
            log_action(db, user_id=created_by_user_id, action="generation.create",
                       entity_type="generation", entity_id=result.db_id)
        except Exception as e:
            repo_jobs.update_status(db, job_id, "error", error_message=str(e))
    finally:
        db.close()


@router.post("/generate")
def generate_content(
    request: Request,
    background_tasks: BackgroundTasks,
    mode: str = Form("long_form"),
    topic: str = Form(...),
    keywords: str = Form(""),
    audience: str = Form("general readers"),
    content_type_key: str = Form("1"),
    tone_key: str = Form("1"),
    platform_key: str = Form("1"),
    page_promoted: str = Form(""),
    chosen_platforms: list[str] = Form([]),
    post_type: str = Form(""),
    caption_goal: str = Form(""),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    plat_name, plat_domain, _pages, _default = pcfg.PLATFORMS[platform_key]
    content_type_name, word_count = pcfg.CONTENT_TYPES[content_type_key]
    tone_name = pcfg.TONES[tone_key]

    params = {
        "mode": mode, "topic": topic, "keywords": keywords, "audience": audience,
        "content_type": content_type_name, "word_count": word_count, "tone": tone_name,
        "plat_name": plat_name, "plat_domain": plat_domain, "page_promoted": page_promoted,
        "chosen_platforms": chosen_platforms, "post_type": post_type, "caption_goal": caption_goal,
    }
    job_type = "social_captions" if mode == "social_captions" else "long_form"
    job = repo_jobs.create_generation_job(db, created_by_user_id=user.id, job_type=job_type, params_json=params)
    background_tasks.add_task(_run_content_job, job.id, params, user.id)

    return render(request, "partials/_progress_sse.html", user=user, job_id=job.id, stream_url=f"/content/generate/{job.id}/stream")


def _poll_job(job_id: uuid.UUID) -> dict:
    db = get_session_factory()()
    try:
        job = repo_jobs.get_generation_job(db, job_id)
        if job is None:
            return {"event": "error", "error": "job not found", "terminal": True}
        if job.status == "done":
            return {"event": "complete", "stage": "done", "redirect": f"/content/{job.result_generation_id}", "terminal": True}
        if job.status == "error":
            return {"event": "error", "stage": "error", "error": job.error_message, "terminal": True}
        return {"event": "stage", "stage": job.status, "terminal": False}
    finally:
        db.close()


@router.get("/generate/{job_id}/stream")
async def stream_content_job(job_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)):
    return StreamingResponse(sse_stream(lambda: _poll_job(job_id)), media_type="text/event-stream")


@router.get("/history")
def content_history(request: Request, db: DbDep, user: CurrentUser = Depends(get_current_user), q: str = ""):
    rows = repo_content.search_generations(db, topic=q or None, limit=20) if q else repo_content.list_recent(db, limit=20)
    return render(request, "partials/_content_history_list.html", user=user, rows=rows)


@router.get("/{generation_id}")
def content_detail(request: Request, generation_id: int, db: DbDep, user: CurrentUser = Depends(get_current_user)):
    generation = repo_content.get_generation(db, generation_id)
    return render(request, "content_detail.html", user=user, generation=generation)
