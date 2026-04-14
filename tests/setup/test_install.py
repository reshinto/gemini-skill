"""Unit tests for ``setup/install.py`` launcher.

Mirrors the ``scripts/health_check.py`` test shape — the launcher is a
thin shim that rejects Python < 3.9 then delegates to
``core.cli.install_main.main``.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "setup" / "install.py"


def _set_compatible_python(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the launcher down the normal non-reexec path."""
    monkeypatch.setattr(sys, "version_info", (3, 13, 2, "final", 0))
    monkeypatch.setattr(sys, "version", "3.13.2 (main, Jan 1 2025, 00:00:00) [Clang]")
    monkeypatch.setattr(sys, "abiflags", "")


class TestInstallLauncher:
    """``setup/install.py`` delegates to core.cli.install_main."""

    def test_main_branch_invokes_core_install_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Running as __main__ calls core.cli.install_main.main with argv[1:]."""
        _set_compatible_python(monkeypatch)
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.install_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["install.py", "--yes"])

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        fake_main.assert_called_once_with(["--yes"])

    def test_import_without_main_does_not_invoke_core(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing (not running as main) skips the delegation."""
        _set_compatible_python(monkeypatch)
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.install_main", fake_module)

        runpy.run_path(str(_SCRIPT_PATH), run_name="install_imported")

        fake_main.assert_not_called()

    def test_version_guard_rejects_old_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The pre-import version check exits cleanly on Python < 3.9."""
        fake_version = (3, 8, 0, "final", 0)
        monkeypatch.setattr(sys, "version_info", fake_version)
        monkeypatch.setattr(sys, "version", "3.8.0 (main, Jan 1 2024, 00:00:00) [Clang]")
        monkeypatch.setattr(sys, "abiflags", "")
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")
        assert "3.9+" in str(exit_info.value)

    def test_repo_root_added_to_syspath(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The launcher prepends the repo root to ``sys.path``."""
        _set_compatible_python(monkeypatch)
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.install_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["install.py"])
        original_path = list(sys.path)

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        expected_root = str(_SCRIPT_PATH.parent.parent)
        assert expected_root in sys.path
        sys.path[:] = original_path

    def test_reexecs_with_first_compatible_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A prerelease free-threaded launcher should re-exec into a stable CPython."""
        monkeypatch.setattr(sys, "version_info", (3, 14, 0, "alpha", 1))
        monkeypatch.setattr(
            sys,
            "version",
            "3.14.0a1 experimental free-threading build (main, Nov 15 2024) [Clang]",
        )
        monkeypatch.setattr(sys, "abiflags", "t")
        monkeypatch.setattr(sys, "argv", ["install.py", "--yes"])

        class FakeProcess:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self._stdout = stdout
                self._stderr = stderr

            def communicate(self):
                return self._stdout, self._stderr

        def fake_popen(cmd, stdout=None, stderr=None):
            del stdout, stderr
            if cmd[0] == "python3.13":
                return FakeProcess(0, b"3|13|2|final||0|CPython\n", b"")
            raise OSError("not found")

        reexec_calls = []

        def fake_execvpe(file, args, env):
            reexec_calls.append((file, args, env))
            raise SystemExit("reexec")

        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("os.execvpe", fake_execvpe)

        with pytest.raises(SystemExit, match="reexec"):
            runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        assert len(reexec_calls) == 1
        file, args, env = reexec_calls[0]
        assert file == "python3.13"
        assert args[0] == "python3.13"
        assert args[1] == str(_SCRIPT_PATH)
        assert args[2:] == ["--yes"]
        assert env["GEMINI_SKILL_INSTALL_REEXEC"] == "python3.13"

    def test_rejects_when_no_compatible_python_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The launcher should surface a clear error when PATH lacks a stable CPython."""
        monkeypatch.setattr(sys, "version_info", (3, 14, 0, "alpha", 1))
        monkeypatch.setattr(
            sys,
            "version",
            "3.14.0a1 experimental free-threading build (main, Nov 15 2024) [Clang]",
        )
        monkeypatch.setattr(sys, "abiflags", "t")

        def fake_popen(cmd, stdout=None, stderr=None):
            del cmd, stdout, stderr
            raise OSError("not found")

        monkeypatch.setattr("subprocess.Popen", fake_popen)

        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        message = str(exit_info.value)
        assert "stable CPython 3.9+" in message
        assert "pre-release builds are not supported" in message
        assert "free-threaded builds are not supported" in message
        assert "Checked on PATH:" in message
