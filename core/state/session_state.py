"""Multi-turn conversation session management.

Stores conversation history (Gemini contents array) per session.
Sessions enable Claude to have iterative dialogues with Gemini —
sending prompts, evaluating responses, and sending follow-ups.

Each session is a separate JSON file in the sessions directory.
Atomic writes with file locking prevent data loss from concurrent access.
Session IDs are validated to prevent path traversal.

Dependencies: core/infra/filelock.py, core/infra/atomic_write.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict, cast

from core.infra.atomic_write import atomic_write_json
from core.infra.filelock import FileLock
from core.transport.base import Content

_LOCK_SUFFIX = ".lock"

# Session IDs: alphanumeric, hyphens, underscores only (1-128 chars)
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class SessionState:
    """Manages multi-turn conversation sessions.

    Each session stores a Gemini-format contents array with alternating
    user/model messages. Sessions are persisted as individual JSON files.
    Session IDs are validated to prevent path traversal attacks.

    Args:
        sessions_dir: Directory for session files.
    """

    def __init__(self, sessions_dir: Path) -> None:
        self._dir = Path(sessions_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """Validate session ID to prevent path traversal.

        Raises:
            ValueError: If the session ID contains unsafe characters.
        """
        if not _SESSION_ID_RE.fullmatch(session_id):
            raise ValueError(
                f"Invalid session_id: {session_id!r}. "
                "Must be 1-128 alphanumeric, hyphen, or underscore characters."
            )

    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self._dir / f"{session_id}.json"

    def _lock_path(self, session_id: str) -> Path:
        """Get the lock file path for a session."""
        return self._dir / f"{session_id}{_LOCK_SUFFIX}"

    def _load(self, session_id: str) -> list[Content]:
        """Load session history from disk."""
        path = self._session_path(session_id)
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "contents" in data:
                contents = data["contents"]
                if isinstance(contents, list):
                    return cast(list[Content], contents)
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save(self, session_id: str, contents: list[Content]) -> None:
        """Atomically write session history to disk under lock."""
        with FileLock(self._lock_path(session_id)):
            data = json.dumps({"contents": contents}, indent=2)
            atomic_write_json(self._session_path(session_id), data)

    def create(self, session_id: str) -> None:
        """Create or reset a session with empty history."""
        self._validate_session_id(session_id)
        self._save(session_id, [])

    def exists(self, session_id: str) -> bool:
        """Check if a session file exists."""
        self._validate_session_id(session_id)
        return self._session_path(session_id).is_file()

    def get_history(self, session_id: str) -> list[Content]:
        """Get the conversation history for a session.

        Returns empty list if session does not exist or is corrupt.
        """
        self._validate_session_id(session_id)
        return self._load(session_id)

    def append_message(self, session_id: str, message: Content) -> None:
        """Append a message to the session history.

        No error if the session does not exist.
        """
        self._validate_session_id(session_id)
        if not self._session_path(session_id).is_file():
            return
        with FileLock(self._lock_path(session_id)):
            contents = self._load(session_id)
            contents.append(message)
            data = json.dumps({"contents": contents}, indent=2)
            atomic_write_json(self._session_path(session_id), data)

    def end_session(self, session_id: str) -> None:
        """Delete a session file. No error if not found."""
        self._validate_session_id(session_id)
        path = self._session_path(session_id)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def list_sessions(self) -> list[str]:
        """Return IDs of all active sessions."""
        return sorted(session_file.stem for session_file in self._dir.glob("*.json"))

    def most_recent(self) -> str | None:
        """Return the ID of the most recently modified session, or None."""
        sessions = list(self._dir.glob("*.json"))
        if not sessions:
            return None
        latest = max(sessions, key=lambda session_path: session_path.stat().st_mtime)
        return latest.stem


class SessionEnvelope(TypedDict):
    """On-disk JSON shape for one persisted session."""

    contents: list[Content]
