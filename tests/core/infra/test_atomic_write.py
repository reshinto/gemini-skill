"""Tests for core/infra/atomic_write.py — shared atomic write utility.

Verifies atomic file creation, permissions, error cleanup paths.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest


class TestAtomicWriteJson:
    """atomic_write_json() must write files atomically with correct perms."""

    def test_creates_file(self, tmp_path):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        atomic_write_json(target, '{"key": "value"}')
        assert target.exists()
        assert target.read_text() == '{"key": "value"}'

    def test_creates_parent_dirs(self, tmp_path):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "sub" / "deep" / "test.json"
        atomic_write_json(target, "{}")
        assert target.exists()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
    def test_sets_file_permissions(self, tmp_path):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        atomic_write_json(target, "{}", file_mode=0o600)
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
    def test_sets_dir_permissions(self, tmp_path):
        from core.infra.atomic_write import atomic_write_json

        sub = tmp_path / "secure"
        target = sub / "test.json"
        atomic_write_json(target, "{}", dir_mode=0o700)
        mode = stat.S_IMODE(sub.stat().st_mode)
        assert mode == 0o700

    def test_overwrites_existing_file(self, tmp_path):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        atomic_write_json(target, '{"v": 1}')
        atomic_write_json(target, '{"v": 2}')
        assert '"v": 2' in target.read_text()

    def test_cleans_up_on_replace_failure(self, tmp_path, monkeypatch):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        monkeypatch.setattr(
            os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed"))
        )
        with pytest.raises(OSError, match="replace failed"):
            atomic_write_json(target, "{}")

    def test_closes_fd_on_write_failure(self, tmp_path, monkeypatch):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        monkeypatch.setattr(
            os, "write", lambda fd, data: (_ for _ in ()).throw(OSError("write failed"))
        )
        with pytest.raises(OSError, match="write failed"):
            atomic_write_json(target, "{}")

    def test_handles_unlink_failure(self, tmp_path, monkeypatch):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        monkeypatch.setattr(
            os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("replace failed"))
        )
        monkeypatch.setattr(os, "unlink", lambda p: (_ for _ in ()).throw(OSError("unlink failed")))
        with pytest.raises(OSError, match="replace failed"):
            atomic_write_json(target, "{}")

    def test_handles_chmod_dir_failure(self, tmp_path, monkeypatch):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        original_chmod = os.chmod
        call_count = [0]

        def failing_chmod(path, mode):
            call_count[0] += 1
            if call_count[0] == 1:  # dir chmod
                raise OSError("dir chmod failed")
            return original_chmod(path, mode)

        monkeypatch.setattr(os, "chmod", failing_chmod)
        # Should not raise — dir chmod is best-effort
        atomic_write_json(target, "{}")
        assert target.exists()

    def test_handles_chmod_file_failure(self, tmp_path, monkeypatch):
        from core.infra.atomic_write import atomic_write_json

        target = tmp_path / "test.json"
        original_chmod = os.chmod
        call_count = [0]

        def failing_chmod(path, mode):
            call_count[0] += 1
            if call_count[0] == 2:  # file chmod
                raise OSError("file chmod failed")
            return original_chmod(path, mode)

        monkeypatch.setattr(os, "chmod", failing_chmod)
        # Should not raise — file chmod is best-effort
        atomic_write_json(target, "{}")
        assert target.exists()
