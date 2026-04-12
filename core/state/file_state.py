"""Files API upload state tracking with 48-hour expiry.

Tracks uploaded file URIs keyed by canonical document identity (SHA-256).
State is stored in files.json with atomic writes and file locking
to handle concurrent Claude Code tool calls safely.

The 48-hour expiry matches the Gemini Files API retention period.
Near-expiry detection enables lazy revalidation before the file expires.

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

# Default near-expiry threshold: 10 minutes before actual expiry
_NEAR_EXPIRY_SECONDS = 600

_STATE_FILENAME = "files.json"
_LOCK_FILENAME = "files.lock"


class FileState:
    """Manages Files API upload state with expiry tracking.

    Each entry maps a document's SHA-256 hash to its Gemini file URI,
    name, and expiry time. Entries are automatically removed when expired.

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
            if isinstance(raw, dict) and "files" in raw:
                return raw["files"]
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save(self) -> None:
        """Atomically write state to disk with file locking."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        with FileLock(self._lock_path):
            data = json.dumps({"files": self._data}, indent=2)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._state_dir), prefix=".files-", suffix=".tmp"
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

    def get_all(self) -> dict[str, Any]:
        """Return all tracked file entries."""
        return dict(self._data)

    def get(self, identity: DocumentIdentity) -> Optional[dict[str, Any]]:
        """Look up a file entry by document identity.

        Args:
            identity: The document identity to look up.

        Returns:
            The entry dict with gemini_uri, gemini_name, expiry, and identity,
            or None if not found.
        """
        return self._data.get(identity.content_sha256)

    def save(
        self,
        identity: DocumentIdentity,
        gemini_uri: str,
        gemini_name: str,
        expiry: float,
    ) -> None:
        """Save or update a file entry.

        Args:
            identity: The canonical document identity.
            gemini_uri: The Gemini file URI (e.g., "files/abc123").
            gemini_name: The Gemini file name.
            expiry: Expiry time as UTC epoch (time.time() based).
        """
        self._data[identity.content_sha256] = {
            "identity": identity.to_dict(),
            "gemini_uri": gemini_uri,
            "gemini_name": gemini_name,
            "expiry": expiry,
        }
        self._save()

    def remove(self, identity: DocumentIdentity) -> None:
        """Remove a file entry by document identity.

        No error if the entry does not exist.
        """
        self._data.pop(identity.content_sha256, None)
        self._save()

    def is_expired(self, identity: DocumentIdentity) -> bool:
        """Check if a file entry has expired or does not exist.

        Args:
            identity: The document identity to check.

        Returns:
            True if expired or not found.
        """
        entry = self.get(identity)
        if entry is None:
            return True
        return time.time() >= entry["expiry"]

    def is_near_expiry(self, identity: DocumentIdentity) -> bool:
        """Check if a file entry is within the near-expiry window.

        Used to trigger lazy revalidation before the file actually expires.
        Returns True if the entry will expire within 10 minutes.

        Args:
            identity: The document identity to check.

        Returns:
            True if near expiry, expired, or not found.
        """
        entry = self.get(identity)
        if entry is None:
            return True
        return time.time() >= entry["expiry"] - _NEAR_EXPIRY_SECONDS

    def cleanup_expired(self) -> int:
        """Remove all expired entries from the state.

        Returns:
            Number of entries removed.
        """
        now = time.time()
        expired_keys = [
            key for key, entry in self._data.items()
            if now >= entry["expiry"]
        ]
        for key in expired_keys:
            del self._data[key]
        if expired_keys:
            self._save()
        return len(expired_keys)
