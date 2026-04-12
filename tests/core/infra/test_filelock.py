"""Tests for core/infra/filelock.py — cross-platform file locking.

Verifies that the FileLock context manager acquires and releases locks,
handles timeouts, and works correctly for concurrent access protection.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest


class TestFileLockBasic:
    """Basic lock acquire/release behavior."""

    def test_lock_acquires_and_releases(self, tmp_path):
        from core.infra.filelock import FileLock

        lock_path = tmp_path / "test.lock"
        with FileLock(lock_path):
            assert lock_path.exists()

    def test_lock_is_context_manager(self):
        from core.infra.filelock import FileLock

        lock = FileLock(Path(tempfile.gettempdir()) / "cm_test.lock")
        assert hasattr(lock, "__enter__")
        assert hasattr(lock, "__exit__")

    def test_lock_releases_on_exception(self, tmp_path):
        from core.infra.filelock import FileLock

        lock_path = tmp_path / "exc_test.lock"
        with pytest.raises(ValueError):
            with FileLock(lock_path):
                raise ValueError("intentional")
        # Lock should be released — we can acquire it again
        with FileLock(lock_path):
            pass

    def test_lock_protects_read_modify_write(self, tmp_path):
        from core.infra.filelock import FileLock

        data_path = tmp_path / "data.json"
        lock_path = tmp_path / "data.lock"
        data_path.write_text('{"count": 0}')

        with FileLock(lock_path):
            data = json.loads(data_path.read_text())
            data["count"] += 1
            data_path.write_text(json.dumps(data))

        result = json.loads(data_path.read_text())
        assert result["count"] == 1


class TestFileLockTimeout:
    """Timeout behavior when lock cannot be acquired."""

    def test_timeout_parameter_accepted(self, tmp_path):
        from core.infra.filelock import FileLock

        lock_path = tmp_path / "timeout.lock"
        with FileLock(lock_path, timeout=1.0):
            pass

    def test_zero_timeout_raises_if_locked(self, tmp_path):
        """A zero timeout should fail immediately if lock is held."""
        from core.infra.filelock import FileLock, LockTimeout

        lock_path = tmp_path / "zero_timeout.lock"
        # Acquire the lock, then try to acquire again with zero timeout
        with FileLock(lock_path):
            with pytest.raises(LockTimeout):
                with FileLock(lock_path, timeout=0):
                    pass


class TestFileLockRetryLoop:
    """Cover the retry sleep and backoff path inside _acquire."""

    def test_short_timeout_retries_then_fails(self, tmp_path):
        """With a very short (but nonzero) timeout, should retry and then fail."""
        from core.infra.filelock import FileLock, LockTimeout

        lock_path = tmp_path / "retry.lock"
        with FileLock(lock_path):
            with pytest.raises(LockTimeout):
                with FileLock(lock_path, timeout=0.15):
                    pass


class TestFileLockRelease:
    """Cover the _release path when fd is None."""

    def test_release_with_no_fd_is_safe(self):
        from core.infra.filelock import FileLock

        lock = FileLock(Path(tempfile.gettempdir()) / "noop.lock")
        # _fd is None by default, calling _release should not error
        lock._release()
