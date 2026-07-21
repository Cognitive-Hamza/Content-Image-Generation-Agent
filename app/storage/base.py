from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Pluggable storage interface. Local filesystem for dev, S3 for prod —
    nothing outside app/storage/ should touch open()/os.path or boto3 directly.
    """

    def save(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        """Write `data` under `key`. Returns the key (may be normalized)."""
        ...

    def get(self, key: str) -> bytes:
        """Read back the bytes stored under `key`. Raises if the key doesn't exist."""
        ...

    def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        """A URL a browser can GET the object from — a presigned S3 URL, or an
        app-served /media/{key} route for the local backend."""
        ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def list(self, prefix: str = "") -> list[str]: ...
