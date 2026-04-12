"""Tests for core/state/store_state.py — File Search store state tracking.

Verifies saving, loading, document tracking, and store management
for persistent File Search stores (no expiry unlike Files API).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest


def _make_identity(sha="abc123"):
    from core.state.identity import DocumentIdentity
    return DocumentIdentity(sha, "application/pdf", f"/tmp/{sha}.pdf", None)


class TestStoreStateLoad:
    """StoreState must load from JSON or return empty state."""

    def test_load_empty_when_no_file(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        assert state.list_stores() == []

    def test_load_existing_state(self, tmp_path):
        from core.state.store_state import StoreState
        data = {
            "stores": {
                "my-store": {
                    "store_id": "fileSearchStores/abc",
                    "documents": {},
                    "created_at": time.time(),
                }
            }
        }
        (tmp_path / "stores.json").write_text(json.dumps(data))
        state = StoreState(state_dir=tmp_path)
        assert "my-store" in state.list_stores()

    def test_load_invalid_json_returns_empty(self, tmp_path):
        from core.state.store_state import StoreState
        (tmp_path / "stores.json").write_text("bad json {")
        state = StoreState(state_dir=tmp_path)
        assert state.list_stores() == []


class TestStoreStateCreate:
    """StoreState.create_store() must register new stores."""

    def test_create_store(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("my-store", "fileSearchStores/abc")
        assert "my-store" in state.list_stores()

    def test_create_store_persists(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("my-store", "fileSearchStores/abc")

        state2 = StoreState(state_dir=tmp_path)
        assert "my-store" in state2.list_stores()

    def test_create_store_sets_id(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("my-store", "fileSearchStores/abc")
        info = state.get_store("my-store")
        assert info["store_id"] == "fileSearchStores/abc"


class TestStoreStateGetStore:
    """StoreState.get_store() must return store info or None."""

    def test_get_existing_store(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")
        info = state.get_store("s1")
        assert info is not None
        assert "store_id" in info

    def test_get_missing_store(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        assert state.get_store("nonexistent") is None


class TestStoreStateDocuments:
    """StoreState must track documents within stores."""

    def test_add_document(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")

        ident = _make_identity()
        state.add_document("s1", ident, operation_name="operations/op1")

        docs = state.list_documents("s1")
        assert len(docs) == 1
        assert docs[0]["identity"]["content_sha256"] == "abc123"

    def test_add_document_with_status(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")

        ident = _make_identity()
        state.add_document("s1", ident, operation_name="ops/1", status="indexing")

        docs = state.list_documents("s1")
        assert docs[0]["status"] == "indexing"

    def test_update_document_status(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")

        ident = _make_identity()
        state.add_document("s1", ident, operation_name="ops/1", status="indexing")
        state.update_document_status("s1", ident, status="completed")

        docs = state.list_documents("s1")
        assert docs[0]["status"] == "completed"

    def test_update_missing_document_no_error(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")
        ident = _make_identity()
        # Should not raise
        state.update_document_status("s1", ident, status="done")

    def test_list_documents_empty_store(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")
        assert state.list_documents("s1") == []

    def test_list_documents_missing_store(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        assert state.list_documents("nonexistent") == []

    def test_has_document_true(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")
        ident = _make_identity()
        state.add_document("s1", ident, operation_name="ops/1")
        assert state.has_document("s1", ident) is True

    def test_has_document_false(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")
        ident = _make_identity()
        assert state.has_document("s1", ident) is False

    def test_has_document_missing_store(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        ident = _make_identity()
        assert state.has_document("nonexistent", ident) is False

    def test_add_document_missing_store_no_error(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        ident = _make_identity()
        state.add_document("nonexistent", ident, operation_name="ops/1")

    def test_update_document_status_missing_store_no_error(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        ident = _make_identity()
        state.update_document_status("nonexistent", ident, status="done")


class TestStoreStateRemove:
    """StoreState.remove_store() must delete stores."""

    def test_remove_store(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.create_store("s1", "fileSearchStores/s1")
        state.remove_store("s1")
        assert state.get_store("s1") is None

    def test_remove_missing_store_no_error(self, tmp_path):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        state.remove_store("nonexistent")  # Should not raise


class TestStoreStateSaveErrors:
    """Cover error paths in _save()."""

    def test_save_cleans_up_on_replace_failure(self, tmp_path, monkeypatch):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        monkeypatch.setattr(os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed")))
        with pytest.raises(OSError, match="replace failed"):
            state.create_store("s1", "fileSearchStores/s1")

    def test_save_closes_fd_on_write_failure(self, tmp_path, monkeypatch):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError("write failed")))
        with pytest.raises(OSError, match="write failed"):
            state.create_store("s1", "fileSearchStores/s1")

    def test_save_handles_unlink_failure(self, tmp_path, monkeypatch):
        from core.state.store_state import StoreState
        state = StoreState(state_dir=tmp_path)
        monkeypatch.setattr(os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed")))
        monkeypatch.setattr(os, "unlink", lambda p: (_ for _ in ()).throw(OSError("unlink failed")))
        with pytest.raises(OSError, match="replace failed"):
            state.create_store("s1", "fileSearchStores/s1")
