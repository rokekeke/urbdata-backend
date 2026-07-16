"""File storage adapters. Original uploads are preserved unmodified (README invariant)."""

from app.infrastructure.storage.local import LocalStorage, StorageBackend

__all__ = ["LocalStorage", "StorageBackend"]
