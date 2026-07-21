from pathlib import Path


class LocalStorageBackend:
    """Filesystem-backed storage for dev. `get_url()` points at the app-served
    /media/{key} route (registered in app/main.py, gated by get_current_user —
    unlike a real S3 bucket, local files aren't public)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError(f"Storage key escapes root: {key}")
        return path

    def save(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"/media/{key}"

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def list(self, prefix: str = "") -> list[str]:
        base = self._path(prefix) if prefix else self.root
        if not base.exists():
            return []
        if base.is_file():
            return [str(base.relative_to(self.root))]
        return [str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file()]
