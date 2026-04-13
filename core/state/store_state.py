"""File Search store state tracking (persistent, no expiry).

Manages the local state of File Search stores created via the Gemini API.
Unlike the Files API (48hr expiry), File Search stores persist indefinitely.
Each store tracks its imported documents and their indexing status.

Every mutating operation re-reads state from disk under the lock
to prevent TOCTOU races from concurrent processes.

Dependencies: core/infra/filelock.py, core/infra/atomic_write.py,
    core/state/identity.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TypedDict, cast

from core.infra.atomic_write import atomic_write_json
from core.infra.filelock import FileLock
from core.state.identity import DocumentIdentity, DocumentIdentityPayload

_STATE_FILENAME = "stores.json"
_LOCK_FILENAME = "stores.lock"


class StoreState:
    """Manages File Search store state with document tracking.

    All mutating operations acquire the file lock and re-read from disk
    to prevent data loss from concurrent access.

    Args:
        state_dir: Directory for state and lock files.
    """

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = Path(state_dir)
        self._state_file = self._state_dir / _STATE_FILENAME
        self._lock_path = self._state_dir / _LOCK_FILENAME

    def _load(self) -> dict[str, StoreRecord]:
        """Load state from disk or return empty structure."""
        if not self._state_file.is_file():
            return {}
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "stores" in raw:
                stores = raw["stores"]
                if isinstance(stores, dict):
                    return cast(dict[str, StoreRecord], stores)
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save(self, data: dict[str, StoreRecord]) -> None:
        """Atomically write state to disk. Must be called under lock."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            self._state_file,
            json.dumps({"stores": data}, indent=2),
        )

    def list_stores(self) -> list[str]:
        """Return names of all tracked stores."""
        return list(self._load().keys())

    def get_store(self, name: str) -> StoreRecord | None:
        """Get store info by name, or None if not found."""
        return self._load().get(name)

    def create_store(self, name: str, store_id: str) -> None:
        """Register a new File Search store under the file lock."""
        with FileLock(self._lock_path):
            data = self._load()
            data[name] = {
                "store_id": store_id,
                "documents": {},
                "created_at": time.time(),
            }
            self._save(data)

    def remove_store(self, name: str) -> None:
        """Remove a store by name. No error if not found."""
        with FileLock(self._lock_path):
            data = self._load()
            data.pop(name, None)
            self._save(data)

    def add_document(
        self,
        store_name: str,
        identity: DocumentIdentity,
        operation_name: str,
        status: str = "pending",
    ) -> None:
        """Track a document imported into a store under the file lock."""
        with FileLock(self._lock_path):
            data = self._load()
            store = data.get(store_name)
            if store is None:
                return
            store["documents"][identity.content_sha256] = {
                "identity": identity.to_dict(),
                "operation_name": operation_name,
                "status": status,
                "added_at": time.time(),
            }
            self._save(data)

    def update_document_status(
        self,
        store_name: str,
        identity: DocumentIdentity,
        status: str,
    ) -> None:
        """Update document indexing status under the file lock."""
        with FileLock(self._lock_path):
            data = self._load()
            store = data.get(store_name)
            if store is None:
                return
            doc = store["documents"].get(identity.content_sha256)
            if doc is None:
                return
            doc["status"] = status
            self._save(data)

    def list_documents(self, store_name: str) -> list[StoreDocumentRecord]:
        """List all documents in a store. Empty list if store not found."""
        store = self._load().get(store_name)
        if store is None:
            return []
        return list(store["documents"].values())

    def has_document(self, store_name: str, identity: DocumentIdentity) -> bool:
        """Check if a document exists in a store."""
        store = self._load().get(store_name)
        if store is None:
            return False
        return identity.content_sha256 in store["documents"]


class StoreDocumentRecord(TypedDict):
    """Tracked status for one document inside a store."""

    identity: DocumentIdentityPayload
    operation_name: str
    status: str
    added_at: float


class StoreRecord(TypedDict):
    """Tracked metadata for one file-search store."""

    store_id: str
    documents: dict[str, StoreDocumentRecord]
    created_at: float
