from fastapi import APIRouter, Depends, Request

from app.auth import CurrentUser, get_current_user
from app.db import repo_content, repo_images
from app.db.audit import log_action
from app.deps import DbDep, StorageDep
from app.templating import render

router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
def history_page(request: Request, db: DbDep, storage: StorageDep, user: CurrentUser = Depends(get_current_user)):
    content_rows = repo_content.list_recent(db, limit=20)
    posts = repo_images.load_all_posts(db, limit=60)
    for p in posts:
        p.image_url = storage.get_url(p.storage_key)
    return render(request, "history.html", user=user, content_rows=content_rows, posts=posts)


@router.get("/content")
def history_content_search(request: Request, db: DbDep, user: CurrentUser = Depends(get_current_user), q: str = ""):
    rows = repo_content.search_generations(db, topic=q or None, limit=20) if q else repo_content.list_recent(db, limit=20)
    return render(request, "partials/_content_history_list.html", user=user, rows=rows)


@router.get("/images")
def history_images_search(request: Request, db: DbDep, storage: StorageDep, user: CurrentUser = Depends(get_current_user), q: str = ""):
    posts = repo_images.load_all_posts(db, limit=200)
    if q:
        needle = q.lower()
        posts = [p for p in posts if needle in (p.headline or "").lower() or needle in (p.sector or "").lower()]
    posts = posts[:60]
    for p in posts:
        p.image_url = storage.get_url(p.storage_key)
    return render(request, "partials/_image_history_grid.html", user=user, posts=posts)


@router.post("/images/{post_id}/delete")
def delete_image(request: Request, post_id: int, db: DbDep, storage: StorageDep, user: CurrentUser = Depends(get_current_user)):
    repo_images.delete_post_from_db(db, storage, post_id)
    log_action(db, user_id=user.id, action="post.delete", entity_type="generated_post", entity_id=post_id)
    return render(request, "partials/_deleted.html", user=user)
