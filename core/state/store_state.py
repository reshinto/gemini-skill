"""File Search store state tracking (persistent, no expiry).

Manages the local state of File Search stores created via the Gemini API.
Unlike the Files API (48hr expiry), File Search stores persist indefinitely.
Each store tracks its imported documents and their indexing status.

Dependencies: core/infra/filelock.py, core/state/identity.py
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from core.infra.filelock import FileLock
from core.state.identity import DocumentIdentity

_STATE_FILENAME = "stores.json"
_LOCK_FILENAME = "stores.lock"


class StoreState:
    """Manages File Search store state with document tracking.

    Each store entry contains:
        - store_id: The Gemini File Search store resource name
        - documents: Map of document SHA-256 to document info
        - created_at: UTC epoch timestamp

    Args:
        state_dir: Directory for state and lock files.
    """

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = Path(state_dir)
        self._state_file = self._state_dir / _STATE_FILENAME
        self._lock_path = self._state_dir / _LOCK_FILENAME
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        """Load state from disk or return empty structure."""
        if not self._state_file.is_file():
            return {}
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "stores" in raw:
                return raw["stores"]
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save(self) -> None:
        """Atomically write state to disk with file locking."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        with FileLock(self._lock_path):
            data = json.dumps({"stores": self._data}, indent=2)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._state_dir), prefix=".stores-", suffix=".tmp"
            )
            try:
                os.write(fd, data.encode("utf-8"))
                os.close(fd)
                fd = -1
                os.replace(tmp_path, str(self._state_file))
            except Exception:
                if fd >= 0:
                    os.close(fd)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    def list_stores(self) -> list[str]:
        """Return names of all tracked stores."""
        return list(self._data.keys())

    def get_store(self, name: str) -> Optional[dict[str, Any]]:
        """Get store info by name, or None if not found."""
        return self._data.get(name)

    def create_store(self, name: str, store_id: str) -> None:
        """Register a new File Search store.

        Args:
            name: Local name for the store.
            store_id: Gemini resource name (e.g., "fileSearchStores/abc").
        """
        self._data[name] = {
            "store_id": store_id,
            "documents": {},
            "created_at": time.time(),
        }
        self._save()

    def remove_store(self, name: str) -> None:
        """Remove a store by name. No error if not found."""
        self._data.pop(name, None)
        self._save()

    def add_document(
        self,
        store_name: str,
        identity: DocumentIdentity,
        operation_name: str,
        status: str = "pending",
    ) -> None:
        """Track a document imported into a store.

        Args:
            store_name: Name of the store.
            identity: Document identity.
            operation_name: Long-running operation name for the import.
            status: Import/indexing status (pending, indexing, completed, failed).
        """
        store = self._data.get(store_name)
        if store is None:
            return
        store["documents"][identity.content_sha256] = {
            "identity": identity.to_dict(),
            "operation_name": operation_name,
            "status": status,
            "added_at": time.time(),
        }
        self._save()

    def update_document_status(
        self,
        store_name: str,
        identity: DocumentIdentity,
        status: str,
    ) -> None:
        """Update the indexing status of a document in a store.

        No error if store or document not found.
        """
        store = self._data.get(store_name)
        if store is None:
            return
        doc = store["documents"].get(identity.content_sha256)
        if doc is None:
            return
        doc["status"] = status
        self._save()

    def list_documents(self, store_name: str) -> list[dict[str, Any]]:
        """List all documents in a store. Empty list if store not found."""
        store = self._data.get(store_name)
        if store is None:
            return []
        return list(store["documents"].values())

    def has_document(self, store_name: str, identity: DocumentIdentity) -> bool:
        """Check if a document exists in a store."""
        store = self._data.get(store_name)
        if store is None:
            return False
        return identity.content_sha256 in store["documents"]
