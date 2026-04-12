"""Multi-turn conversation session management.

Stores conversation history (Gemini contents array) per session.
Sessions enable Claude to have iterative dialogues with Gemini —
sending prompts, evaluating responses, and sending follow-ups.

Each session is a separate JSON file in the sessions directory.
Atomic writes with file locking prevent data loss from concurrent access.

Dependencies: core/infra/filelock.py
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from core.infra.filelock import FileLock

_LOCK_SUFFIX = ".lock"


class SessionState:
    """Manages multi-turn conversation sessions.

    Each session stores a Gemini-format contents array with alternating
    user/model messages. Sessions are persisted as individual JSON files.

    Args:
        sessions_dir: Directory for session files.
    """

    def __init__(self, sessions_dir: Path) -> None:
        self._dir = Path(sessions_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self._dir / f"{session_id}.json"

    def _lock_path(self, session_id: str) -> Path:
        """Get the lock file path for a session."""
        return self._dir / f"{session_id}{_LOCK_SUFFIX}"

    def _load(self, session_id: str) -> list[dict[str, Any]]:
        """Load session history from disk."""
        path = self._session_path(session_id)
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "contents" in data:
                return data["contents"]
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save(self, session_id: str, contents: list[dict[str, Any]]) -> None:
        """Atomically write session history to disk."""
        with FileLock(self._lock_path(session_id)):
            data = json.dumps({"contents": contents}, indent=2)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._dir), prefix=f".session-{session_id}-", suffix=".tmp"
            )
            try:
                os.write(fd, data.encode("utf-8"))
                os.close(fd)
                fd = -1
                os.replace(tmp_path, str(self._session_path(session_id)))
            except Exception:
                if fd >= 0:
                    os.close(fd)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    def create(self, session_id: str) -> None:
        """Create or reset a session with empty history."""
        self._save(session_id, [])

    def exists(self, session_id: str) -> bool:
        """Check if a session file exists."""
        return self._session_path(session_id).is_file()

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get the conversation history for a session.

        Returns empty list if session does not exist or is corrupt.
        """
        return self._load(session_id)

    def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Append a message to the session history.

        No error if the session does not exist.

        Args:
            session_id: The session identifier.
            message: A Gemini-format message dict with role and parts.
        """
        if not self.exists(session_id):
            return
        contents = self._load(session_id)
        contents.append(message)
        self._save(session_id, contents)

    def end_session(self, session_id: str) -> None:
        """Delete a session file. No error if not found."""
        path = self._session_path(session_id)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def list_sessions(self) -> list[str]:
        """Return IDs of all active sessions."""
        return sorted(
            p.stem for p in self._dir.glob("*.json")
        )

    def most_recent(self) -> Optional[str]:
        """Return the ID of the most recently modified session, or None."""
        sessions = list(self._dir.glob("*.json"))
        if not sessions:
            return None
        latest = max(sessions, key=lambda p: p.stat().st_mtime)
        return latest.stem
