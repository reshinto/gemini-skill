"""Files API upload state tracking with 48-hour expiry.

Tracks uploaded file URIs keyed by canonical document identity (SHA-256).
State is stored in files.json with atomic writes and file locking
to handle concurrent Claude Code tool calls safely.

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

# Default near-expiry threshold: 10 minutes before actual expiry
_NEAR_EXPIRY_SECONDS = 600

_STATE_FILENAME = "files.json"
_LOCK_FILENAME = "files.lock"


class FileState:
    """Manages Files API upload state with expiry tracking.

    Each entry maps a document's SHA-256 hash to its Gemini file URI,
    name, and expiry time. Entries are automatically removed when expired.

    All mutating operations acquire the file lock and re-read from disk
    to prevent data loss from concurrent access.

    Args:
        state_dir: Directory for state and lock files.
    """

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = Path(state_dir)
        self._state_file = self._state_dir / _STATE_FILENAME
        self._lock_path = self._state_dir / _LOCK_FILENAME

    def _load(self) -> dict[str, FileRecord]:
        """Load state from disk or return empty structure."""
        if not self._state_file.is_file():
            return {}
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "files" in raw:
                files = raw["files"]
                if isinstance(files, dict):
                    return cast(dict[str, FileRecord], files)
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save(self, data: dict[str, FileRecord]) -> None:
        """Atomically write state to disk. Must be called under lock."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            self._state_file,
            json.dumps({"files": data}, indent=2),
        )

    def get_all(self) -> dict[str, FileRecord]:
        """Return all tracked file entries."""
        return dict(self._load())

    def get(self, identity: DocumentIdentity) -> FileRecord | None:
        """Look up a file entry by document identity."""
        return self._load().get(identity.content_sha256)

    def save(
        self,
        identity: DocumentIdentity,
        gemini_uri: str,
        gemini_name: str,
        expiry: float,
    ) -> None:
        """Save or update a file entry under the file lock.

        Re-reads from disk to prevent TOCTOU races.
        """
        with FileLock(self._lock_path):
            data = self._load()
            data[identity.content_sha256] = {
                "identity": identity.to_dict(),
                "gemini_uri": gemini_uri,
                "gemini_name": gemini_name,
                "expiry": expiry,
            }
            self._save(data)

    def remove(self, identity: DocumentIdentity) -> None:
        """Remove a file entry. No error if not found."""
        with FileLock(self._lock_path):
            data = self._load()
            data.pop(identity.content_sha256, None)
            self._save(data)

    def is_expired(self, identity: DocumentIdentity) -> bool:
        """Check if a file entry has expired or does not exist."""
        entry = self.get(identity)
        if entry is None:
            return True
        return time.time() >= entry["expiry"]

    def is_near_expiry(self, identity: DocumentIdentity) -> bool:
        """Check if a file entry is within the near-expiry window (10 min)."""
        entry = self.get(identity)
        if entry is None:
            return True
        return time.time() >= entry["expiry"] - _NEAR_EXPIRY_SECONDS

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with FileLock(self._lock_path):
            data = self._load()
            now = time.time()
            expired_keys = [key for key, entry in data.items() if now >= entry["expiry"]]
            for key in expired_keys:
                del data[key]
            if expired_keys:
                self._save(data)
            return len(expired_keys)


class FileRecord(TypedDict):
    """One tracked uploaded file entry."""

    identity: DocumentIdentityPayload
    gemini_uri: str
    gemini_name: str
    expiry: float
