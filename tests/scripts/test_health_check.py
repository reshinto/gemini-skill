"""Unit tests for the ``scripts/health_check.py`` launcher.

The launcher is a Python 2.7-safe shim that:
1. Rejects Python < 3.9 with a readable message.
2. Bootstraps runtime env from the current working directory / Claude settings.
3. Inserts the repo root onto ``sys.path``.
4. Delegates to ``core.cli.health_main.main`` with ``sys.argv[1:]``.

These tests cover all four paths via ``runpy.run_path`` so the
``if __name__ == "__main__"`` branch is exercised — giving the
launcher 100% line + branch coverage.
"""

from __future__ import annotations

import runpy
import sys
from types import ModuleType
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "health_check.py"


def _import_runner() -> ModuleType:
    import importlib.util

    spec = importlib.util.spec_from_file_location("health_check_test", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestHealthCheckLauncher:
    """``scripts/health_check.py`` delegates to core.cli.health_main."""

    def test_main_calls_bootstrap_before_health_main(self) -> None:
        runner = _import_runner()
        call_order: list[str] = []

        def record_bootstrap() -> None:
            call_order.append("bootstrap")

        def record_health_main(arguments: list[str]) -> None:
            call_order.append("health")

        fake_module = MagicMock()
        fake_module.main = record_health_main

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setitem(sys.modules, "core.cli.health_main", fake_module)
            monkeypatch.setattr(runner, "_bootstrap_runtime_environment", record_bootstrap)
            runner.main(["--verbose"])

        assert call_order == ["bootstrap", "health"]

    def test_main_branch_invokes_core_health_main(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running as __main__ calls core.cli.health_main.main with argv[1:]."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.health_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["health_check.py", "--verbose"])
        home_directory: Path = tmp_path / "home"
        home_directory.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(home_directory))

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        fake_main.assert_called_once_with(["--verbose"])

    def test_import_without_main_does_not_invoke_core(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running with a non-__main__ name skips the delegation."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.health_main", fake_module)
        home_directory: Path = tmp_path / "home"
        home_directory.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(home_directory))

        runpy.run_path(str(_SCRIPT_PATH), run_name="health_check_imported")

        fake_main.assert_not_called()

    def test_version_guard_rejects_old_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The pre-import version check exits cleanly on Python < 3.9."""
        fake_version = (3, 8, 0, "final", 0)
        monkeypatch.setattr(sys, "version_info", fake_version)
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")
        assert "3.9+" in str(exit_info.value)

    def test_repo_root_added_to_syspath(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The launcher prepends the repo root to ``sys.path``."""
        fake_main = MagicMock(return_value=None)
        fake_module = MagicMock()
        fake_module.main = fake_main
        monkeypatch.setitem(sys.modules, "core.cli.health_main", fake_module)
        monkeypatch.setattr(sys, "argv", ["health_check.py"])
        home_directory: Path = tmp_path / "home"
        home_directory.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(home_directory))
        # Snapshot sys.path so we can see what the launcher added.
        original_path = list(sys.path)

        runpy.run_path(str(_SCRIPT_PATH), run_name="__main__")

        expected_root = str(_SCRIPT_PATH.parent.parent)
        assert expected_root in sys.path
        # Restore (monkeypatch doesn't auto-restore sys.path mutations)
        sys.path[:] = original_path

    def test_ensure_repo_root_on_syspath_inserts_missing_root(self) -> None:
        runner = _import_runner()
        expected_root: str = runner._repo_root()

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                sys, "path", [entry for entry in sys.path if entry != expected_root]
            )
            resolved_root: str = runner._ensure_repo_root_on_syspath()

            assert resolved_root == expected_root
            assert sys.path[0] == expected_root

    def test_bootstrap_runtime_environment_exits_cleanly_on_resolution_error(self) -> None:
        runner = _import_runner()
        from core.infra.errors import EnvironmentResolutionError

        def ensure_repo_root_on_syspath() -> str:
            return str(_SCRIPT_PATH.parent.parent)

        def raise_resolution_error() -> dict[str, str]:
            raise EnvironmentResolutionError("bad settings")

        with (
            pytest.MonkeyPatch.context() as monkeypatch,
            pytest.raises(SystemExit, match="bad settings"),
        ):
            monkeypatch.setattr(runner, "_ensure_repo_root_on_syspath", ensure_repo_root_on_syspath)
            monkeypatch.setattr(
                "core.infra.runtime_env.bootstrap_runtime_env", raise_resolution_error
            )
            runner._bootstrap_runtime_environment()
