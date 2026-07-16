import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config.settings import get_settings


class StorageBackend(Protocol):
    def save(self, stream: BinaryIO, *, filename: str, subpath: str) -> str: ...

    def read(self, stored_path: str) -> bytes: ...


class LocalStorage:
    """Disk-backed storage for original uploads. Swappable for object storage later."""

    def __init__(self, base_path: str | None = None) -> None:
        self._base_path = Path(base_path or get_settings().storage_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def save(self, stream: BinaryIO, *, filename: str, subpath: str) -> str:
        target_dir = self._base_path / subpath
        target_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4()}_{filename}"
        target_path = target_dir / stored_name
        with target_path.open("wb") as destination:
            shutil.copyfileobj(stream, destination)
        return str(target_path.relative_to(self._base_path))

    def read(self, stored_path: str) -> bytes:
        return (self._base_path / stored_path).read_bytes()
