"""Tests for core/state/session_state.py — multi-turn conversation sessions.

Verifies session creation, appending messages, loading history,
ending sessions, and listing active sessions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


class TestSessionCreate:
    """SessionState must create and persist sessions."""

    def test_create_session(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("review-1")
        assert state.exists("review-1")

    def test_create_session_persists_file(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        assert (tmp_path / "s1.json").exists()

    def test_create_session_empty_history(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        history = state.get_history("s1")
        assert history == []

    def test_create_overwrites_existing(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        state.append_message("s1", {"role": "user", "parts": [{"text": "hi"}]})
        state.create("s1")  # Reset
        assert state.get_history("s1") == []


class TestSessionAppend:
    """SessionState.append_message() must add to conversation history."""

    def test_append_user_message(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        msg = {"role": "user", "parts": [{"text": "hello"}]}
        state.append_message("s1", msg)

        history = state.get_history("s1")
        assert len(history) == 1
        assert history[0]["role"] == "user"

    def test_append_model_response(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        state.append_message("s1", {"role": "user", "parts": [{"text": "hi"}]})
        state.append_message("s1", {"role": "model", "parts": [{"text": "hello!"}]})

        history = state.get_history("s1")
        assert len(history) == 2
        assert history[1]["role"] == "model"

    def test_append_persists_across_loads(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        state.append_message("s1", {"role": "user", "parts": [{"text": "hi"}]})

        state2 = SessionState(sessions_dir=tmp_path)
        history = state2.get_history("s1")
        assert len(history) == 1

    def test_append_to_nonexistent_session_no_error(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        # Should not raise — just silently ignore
        state.append_message("nonexistent", {"role": "user", "parts": [{"text": "hi"}]})


class TestSessionGetHistory:
    """SessionState.get_history() must return conversation contents array."""

    def test_get_history_empty(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        assert state.get_history("s1") == []

    def test_get_history_missing_session(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        assert state.get_history("nonexistent") == []

    def test_get_history_corrupt_file(self, tmp_path):
        from core.state.session_state import SessionState
        (tmp_path / "bad.json").write_text("not json {{{")
        state = SessionState(sessions_dir=tmp_path)
        assert state.get_history("bad") == []


class TestSessionEnd:
    """SessionState.end_session() must remove session files."""

    def test_end_session_removes_file(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        state.end_session("s1")
        assert not (tmp_path / "s1.json").exists()

    def test_end_session_not_exists_no_error(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.end_session("nonexistent")  # Should not raise

    def test_exists_false_after_end(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        state.end_session("s1")
        assert state.exists("s1") is False


class TestSessionList:
    """SessionState.list_sessions() must return active session IDs."""

    def test_list_empty(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        assert state.list_sessions() == []

    def test_list_active_sessions(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("a")
        state.create("b")
        sessions = state.list_sessions()
        assert set(sessions) == {"a", "b"}

    def test_list_excludes_ended(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("a")
        state.create("b")
        state.end_session("a")
        assert state.list_sessions() == ["b"]


class TestSessionMostRecent:
    """SessionState.most_recent() must return the latest session ID."""

    def test_most_recent_returns_latest(self, tmp_path):
        from core.state.session_state import SessionState
        import time
        state = SessionState(sessions_dir=tmp_path)
        state.create("old")
        # Ensure different mtime
        time.sleep(0.05)
        state.create("new")
        assert state.most_recent() == "new"

    def test_most_recent_none_when_empty(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        assert state.most_recent() is None


class TestSessionIdValidation:
    """SessionState must reject unsafe session IDs."""

    def test_rejects_path_traversal(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        with pytest.raises(ValueError, match="Invalid session_id"):
            state.create("../../../etc/passwd")

    def test_rejects_slashes(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        with pytest.raises(ValueError, match="Invalid session_id"):
            state.create("foo/bar")

    def test_rejects_empty_string(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        with pytest.raises(ValueError, match="Invalid session_id"):
            state.create("")

    def test_accepts_valid_ids(self, tmp_path):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        for sid in ["review-1", "my_session", "abc123", "A-B_C"]:
            state.create(sid)
            assert state.exists(sid)


class TestSessionSaveErrors:
    """Cover error paths in _save()."""

    def test_save_cleans_up_on_replace_failure(self, tmp_path, monkeypatch):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        monkeypatch.setattr(os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed")))
        with pytest.raises(OSError, match="replace failed"):
            state.append_message("s1", {"role": "user", "parts": [{"text": "hi"}]})

    def test_save_closes_fd_on_write_failure(self, tmp_path, monkeypatch):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError("write failed")))
        with pytest.raises(OSError, match="write failed"):
            state.append_message("s1", {"role": "user", "parts": [{"text": "hi"}]})

    def test_save_handles_unlink_failure(self, tmp_path, monkeypatch):
        from core.state.session_state import SessionState
        state = SessionState(sessions_dir=tmp_path)
        state.create("s1")
        monkeypatch.setattr(os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed")))
        monkeypatch.setattr(os, "unlink", lambda p: (_ for _ in ()).throw(OSError("unlink failed")))
        with pytest.raises(OSError, match="replace failed"):
            state.append_message("s1", {"role": "user", "parts": [{"text": "hi"}]})
