from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.storage import get_storage_backend
from app.storage.base import StorageBackend


def get_storage() -> StorageBackend:
    return get_storage_backend()


DbDep = Annotated[Session, Depends(get_db)]
StorageDep = Annotated[StorageBackend, Depends(get_storage)]
