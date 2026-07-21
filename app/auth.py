from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import get_db
from app.db.models import User


class CurrentUser(BaseModel):
    id: int
    email: str
    display_name: str | None = None
    auth_source: Literal["header", "jwt", "dev"]


def validate_auth_config() -> None:
    """Called once at app startup. Refuses to boot into a misconfigured state
    rather than silently falling back — this is the first of two fail-closed
    checks; get_current_user() re-checks at request time as well."""
    settings = get_settings()
    if settings.AUTH_MODE == "dev" and settings.ENV != "dev":
        raise RuntimeError(
            "AUTH_MODE=dev is not permitted outside ENV=dev — refusing to start. "
            "Set AUTH_MODE to 'header' or 'jwt' for staging/prod deployments."
        )
    if settings.AUTH_MODE == "jwt" and not (settings.AUTH_JWT_SECRET or settings.AUTH_JWT_JWKS_URL):
        raise RuntimeError("AUTH_MODE=jwt requires AUTH_JWT_SECRET or AUTH_JWT_JWKS_URL to be set")


def _verify_jwt_and_extract_email(request: Request) -> str:
    from jose import JWTError, jwt

    settings = get_settings()
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        if settings.AUTH_JWT_SECRET:
            claims = jwt.decode(token, settings.AUTH_JWT_SECRET, options={"verify_aud": False})
        else:
            # JWKS-based verification, resolved lazily at request time (not at
            # import/startup) so app boot never makes a network call.
            import requests

            jwks = requests.get(settings.AUTH_JWT_JWKS_URL, timeout=5).json()
            header = jwt.get_unverified_header(token)
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
            if key is None:
                raise HTTPException(status_code=401, detail="Unknown signing key")
            claims = jwt.decode(token, key, options={"verify_aud": False})
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = claims.get(settings.AUTH_JWT_EMAIL_CLAIM)
    if not email:
        raise HTTPException(
            status_code=401, detail=f"Token missing '{settings.AUTH_JWT_EMAIL_CLAIM}' claim"
        )
    return email


def _get_or_create_user(db: Session, email: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if user is None:
        user = User(email=email, created_at=now, last_seen_at=now)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.last_seen_at is None or now - user.last_seen_at > timedelta(minutes=5):
        user.last_seen_at = now
        db.commit()
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    """Resolves identity per AUTH_MODE. Fails closed: any mode with no
    resolvable email is always a 401, never a silent anonymous pass-through."""
    settings = get_settings()
    mode = settings.AUTH_MODE

    if mode == "header":
        email = request.headers.get(settings.AUTH_HEADER_NAME)
        if not email:
            raise HTTPException(
                status_code=401, detail=f"Missing identity header: {settings.AUTH_HEADER_NAME}"
            )
        source: Literal["header", "jwt", "dev"] = "header"
    elif mode == "jwt":
        email = _verify_jwt_and_extract_email(request)
        source = "jwt"
    elif mode == "dev":
        if settings.ENV != "dev":
            # validate_auth_config() already refuses to boot in this state —
            # this is the request-time half of the fail-closed guarantee.
            raise HTTPException(status_code=401, detail="AUTH_MODE=dev is not permitted outside ENV=dev")
        email = settings.DEV_USER_EMAIL
        if not email:
            raise HTTPException(status_code=401, detail="DEV_USER_EMAIL not set")
        source = "dev"
    else:
        raise HTTPException(status_code=401, detail=f"Unknown AUTH_MODE: {mode}")

    user = _get_or_create_user(db, email)
    return CurrentUser(id=user.id, email=user.email, display_name=user.display_name, auth_source=source)
