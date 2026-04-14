"""Unit tests for the ``scripts/health_check.py`` launcher.

The launcher is a Python 2.7-safe shim that:
1. Rejects Python < 3.9 with a readable message.
2. Inserts the repo root onto ``sys.path``.
3. Delegates to ``core.cli.health_main.main`` with ``sys.argv[1:]``.

These tests cover all three paths via ``runpy.run_path`` so the
``if __name__ == "__main__"`` branch is exercised — giving the
launcher 100% line + branch coverage.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "health_check.py"


class TestHealthCheckLauncher:
    """``scripts/health_check.py`` delegates to core.cli.health_main."""

    def test_main_branch_invokes_core_health_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Running as __main__ calls core.cli.health_main.main with argv[1:]."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.health_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["health_check.py", "--verbose"])

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        fake_main.assert_called_once_with(["--verbose"])

    def test_import_without_main_does_not_invoke_core(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running with a non-__main__ name skips the delegation."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.health_main", fake_module)

        runpy.run_path(str(_SCRIPT_PATH), run_name="health_check_imported")

        fake_main.assert_not_called()

    def test_version_guard_rejects_old_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The pre-import version check exits cleanly on Python < 3.9."""
        fake_version = (3, 8, 0, "final", 0)
        monkeypatch.setattr(sys, "version_info", fake_version)
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")
        assert "3.9+" in str(exit_info.value)

    def test_repo_root_added_to_syspath(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The launcher prepends the repo root to ``sys.path``."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.health_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["health_check.py"])
        # Snapshot sys.path so we can see what the launcher added.
        original_path = list(sys.path)

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        expected_root = str(_SCRIPT_PATH.parent.parent)
        assert expected_root in sys.path
        # Restore (monkeypatch doesn't auto-restore sys.path mutations)
        sys.path[:] = original_path
