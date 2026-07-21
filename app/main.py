import mimetypes
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import CurrentUser, get_current_user, validate_auth_config
from app.config import get_settings
from app.db.base import get_db
from app.deps import StorageDep

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    validate_auth_config()  # fail closed at boot — see app/auth.py

    app = FastAPI(title="Al-Nafi Content & Image Generation")

    # Narrow, one-shot flash-message session only — not a general state bag.
    # See app/auth.py / plan Phase 2 notes for why per-request DB reads are
    # preferred over session state for everything else.
    app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/healthz")
    def healthz(db: Session = Depends(get_db)):
        db.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/media/{key:path}")
    def media(key: str, storage: StorageDep, user: CurrentUser = Depends(get_current_user)):
        """Serves local-backend storage objects. Gated by auth — unlike a real
        S3 bucket, files on the local disk backend aren't public by default."""
        if not storage.exists(key):
            raise HTTPException(status_code=404)
        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        return Response(content=storage.get(key), media_type=content_type)

    from app.routes import content, history, image, landing, translate

    app.include_router(landing.router)
    app.include_router(content.router)
    app.include_router(image.router)
    app.include_router(translate.router)
    app.include_router(history.router)

    return app


app = create_app()
