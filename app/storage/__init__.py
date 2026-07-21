from functools import lru_cache

from app.config import get_settings
from app.storage.base import StorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.STORAGE_BACKEND == "s3":
        from app.storage.s3 import S3StorageBackend

        if not settings.S3_BUCKET:
            raise RuntimeError("STORAGE_BACKEND=s3 requires S3_BUCKET to be set")
        return S3StorageBackend(
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
        )
    elif settings.STORAGE_BACKEND == "local":
        from app.storage.local import LocalStorageBackend

        return LocalStorageBackend(settings.STORAGE_LOCAL_ROOT)
    else:
        raise RuntimeError(f"Unknown STORAGE_BACKEND: {settings.STORAGE_BACKEND}")
