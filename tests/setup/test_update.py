"""Unit tests for ``setup/update.py`` launcher.

Mirror of ``tests/setup/test_install.py`` — same shape, different target.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "setup" / "update.py"


class TestUpdateLauncher:
    """``setup/update.py`` delegates to core.cli.update_main."""

    def test_main_branch_invokes_core_update_main(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running as __main__ calls core.cli.update_main.main with argv[1:]."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.update_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["update.py"])

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        fake_main.assert_called_once_with([])

    def test_import_without_main_does_not_invoke_core(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing (not running as main) skips the delegation."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.update_main", fake_module)

        runpy.run_path(str(_SCRIPT_PATH), run_name="update_imported")

        fake_main.assert_not_called()

    def test_version_guard_rejects_old_python(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The pre-import version check exits cleanly on Python < 3.9."""
        fake_version = (3, 8, 0, "final", 0)
        monkeypatch.setattr(sys, "version_info", fake_version)
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")
        assert "3.9+" in str(exit_info.value)

    def test_repo_root_added_to_syspath(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The launcher prepends the repo root to ``sys.path``."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.update_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["update.py"])
        original_path = list(sys.path)

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        expected_root = str(_SCRIPT_PATH.parent.parent)
        assert expected_root in sys.path
        sys.path[:] = original_path
