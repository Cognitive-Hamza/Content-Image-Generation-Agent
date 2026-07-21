from datetime import datetime
from functools import lru_cache

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

SCHEMA = "cig"


class Base(DeclarativeBase):
    metadata_schema = SCHEMA
    # Every Mapped[datetime] column is timezone-aware (TIMESTAMPTZ) by default —
    # without this, Postgres round-trips naive datetimes and any comparison
    # against datetime.now(timezone.utc) raises TypeError.
    type_annotation_map = {datetime: DateTime(timezone=True)}


Base.metadata.schema = SCHEMA


@lru_cache
def get_engine():
    return create_engine(get_settings().DATABASE_URL, pool_pre_ping=True, future=True)


@lru_cache
def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_db():
    """FastAPI dependency: yields a Session, always closed after the request."""
    db: Session = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
