"""Tests for core/state/file_state.py — Files API upload state tracking.

Verifies saving, loading, expiry checking, cleanup, and file-locked
atomic writes for the upload state store.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest


def _make_identity():
    """Helper to create a DocumentIdentity for testing."""
    from core.state.identity import DocumentIdentity

    return DocumentIdentity(
        content_sha256="abc123def456",
        mime_type="application/pdf",
        source_path="/tmp/doc.pdf",
        source_uri=None,
    )


class TestFileStateLoad:
    """FileState must load from JSON or return empty state."""

    def test_load_empty_when_no_file(self, tmp_path):
        from core.state.file_state import FileState

        state = FileState(state_dir=tmp_path)
        assert state.get_all() == {}

    def test_load_existing_state(self, tmp_path):
        from core.state.file_state import FileState

        data = {
            "files": {
                "abc123def456": {
                    "identity": {
                        "content_sha256": "abc123def456",
                        "mime_type": "application/pdf",
                        "source_path": "/tmp/doc.pdf",
                        "source_uri": None,
                    },
                    "gemini_uri": "files/xyz",
                    "gemini_name": "files/xyz",
                    "expiry": time.time() + 3600,
                }
            }
        }
        (tmp_path / "files.json").write_text(json.dumps(data))

        state = FileState(state_dir=tmp_path)
        all_files = state.get_all()
        assert "abc123def456" in all_files

    def test_load_invalid_json_returns_empty(self, tmp_path):
        from core.state.file_state import FileState

        (tmp_path / "files.json").write_text("not json {{{")

        state = FileState(state_dir=tmp_path)
        assert state.get_all() == {}


class TestFileStateSave:
    """FileState must save entries with atomic writes."""

    def test_save_and_reload(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        expiry = time.time() + 48 * 3600

        state.save(identity, gemini_uri="files/abc", gemini_name="files/abc", expiry=expiry)

        # Reload from disk
        state2 = FileState(state_dir=tmp_path)
        entry = state2.get(identity)
        assert entry is not None
        assert entry["gemini_uri"] == "files/abc"

    def test_save_creates_state_file(self, tmp_path):
        from core.state.file_state import FileState

        state = FileState(state_dir=tmp_path)
        identity = _make_identity()
        state.save(identity, gemini_uri="files/x", gemini_name="files/x", expiry=time.time() + 3600)

        assert (tmp_path / "files.json").exists()

    def test_save_overwrites_existing_entry(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)

        state.save(
            identity, gemini_uri="files/old", gemini_name="files/old", expiry=time.time() + 3600
        )
        state.save(
            identity, gemini_uri="files/new", gemini_name="files/new", expiry=time.time() + 7200
        )

        entry = state.get(identity)
        assert entry["gemini_uri"] == "files/new"


class TestFileStateGet:
    """FileState.get() must return entries or None."""

    def test_get_returns_none_for_missing(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        assert state.get(identity) is None

    def test_get_returns_valid_entry(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        state.save(
            identity, gemini_uri="files/abc", gemini_name="files/abc", expiry=time.time() + 3600
        )

        entry = state.get(identity)
        assert entry is not None
        assert entry["gemini_name"] == "files/abc"


class TestFileStateExpiry:
    """FileState must handle expired entries correctly."""

    def test_is_expired_true_for_past(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        state.save(identity, gemini_uri="files/x", gemini_name="files/x", expiry=time.time() - 10)

        assert state.is_expired(identity) is True

    def test_is_expired_false_for_future(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        state.save(identity, gemini_uri="files/x", gemini_name="files/x", expiry=time.time() + 3600)

        assert state.is_expired(identity) is False

    def test_is_expired_true_for_missing(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        assert state.is_expired(identity) is True

    def test_near_expiry_threshold(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        # Expires in 5 minutes — within the near-expiry window (default 10 min)
        state.save(identity, gemini_uri="files/x", gemini_name="files/x", expiry=time.time() + 300)

        assert state.is_near_expiry(identity) is True

    def test_not_near_expiry(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        state.save(identity, gemini_uri="files/x", gemini_name="files/x", expiry=time.time() + 7200)

        assert state.is_near_expiry(identity) is False

    def test_near_expiry_missing_entry(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        assert state.is_near_expiry(identity) is True


class TestFileStateCleanup:
    """FileState.cleanup_expired() must remove stale entries."""

    def test_cleanup_removes_expired(self, tmp_path):
        from core.state.file_state import FileState
        from core.state.identity import DocumentIdentity

        state = FileState(state_dir=tmp_path)

        ident_expired = DocumentIdentity("hash1", "text/plain", "/a.txt", None)
        ident_valid = DocumentIdentity("hash2", "text/plain", "/b.txt", None)

        state.save(ident_expired, "files/a", "files/a", expiry=time.time() - 10)
        state.save(ident_valid, "files/b", "files/b", expiry=time.time() + 3600)

        removed = state.cleanup_expired()
        assert removed == 1
        assert state.get(ident_expired) is None
        assert state.get(ident_valid) is not None

    def test_cleanup_returns_zero_when_none_expired(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        state.save(identity, "files/x", "files/x", expiry=time.time() + 3600)

        removed = state.cleanup_expired()
        assert removed == 0


class TestFileStateRemove:
    """FileState.remove() must delete entries."""

    def test_remove_existing(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        state.save(identity, "files/x", "files/x", expiry=time.time() + 3600)

        state.remove(identity)
        assert state.get(identity) is None

    def test_remove_missing_no_error(self, tmp_path):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)
        state.remove(identity)  # Should not raise


class TestFileStateSaveErrors:
    """Cover error paths in _save()."""

    def test_save_cleans_up_on_replace_failure(self, tmp_path, monkeypatch):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)

        monkeypatch.setattr(
            os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed"))
        )
        with pytest.raises(OSError, match="replace failed"):
            state.save(identity, "files/x", "files/x", expiry=time.time() + 3600)

    def test_save_closes_fd_on_write_failure(self, tmp_path, monkeypatch):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)

        monkeypatch.setattr(
            os, "write", lambda fd, data: (_ for _ in ()).throw(OSError("write failed"))
        )
        with pytest.raises(OSError, match="write failed"):
            state.save(identity, "files/x", "files/x", expiry=time.time() + 3600)

    def test_save_handles_unlink_failure(self, tmp_path, monkeypatch):
        from core.state.file_state import FileState

        identity = _make_identity()
        state = FileState(state_dir=tmp_path)

        monkeypatch.setattr(
            os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed"))
        )
        monkeypatch.setattr(os, "unlink", lambda p: (_ for _ in ()).throw(OSError("unlink failed")))
        with pytest.raises(OSError, match="replace failed"):
            state.save(identity, "files/x", "files/x", expiry=time.time() + 3600)
