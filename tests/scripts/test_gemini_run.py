"""Tests for scripts/gemini_run.py — the SKILL.md launcher.

The launcher is invoked from SKILL.md (and the standalone test
runner). Phase 5 adds a venv re-exec hook so users running the
installed skill always run under the skill-local ``.venv/bin/python``
even if they invoke gemini_run.py with a different Python.

The re-exec contract:

1. If ``sys.executable`` is already the venv's python, no-op.
2. If the venv exists at ``<install_dir>/.venv`` and we're NOT
   running under it, ``os.execv`` into the venv python.
3. If no venv exists (e.g. local-dev mode running from a repo
   clone), continue without re-exec — the dev's repo-root .venv
   handles dependency isolation.

Tests mock ``os.execv``, ``sys.executable``, and ``Path.exists``
because actually exec'ing in a test would terminate the test
runner.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from pathlib import Path
from unittest import mock

import pytest


def _import_runner() -> ModuleType:
    """Reload scripts.gemini_run cleanly so each test sees fresh module state."""
    # The launcher script lives at scripts/gemini_run.py — it isn't
    # part of any package, so we import it via importlib from a
    # constructed module spec to avoid polluting sys.modules state
    # between tests.
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "gemini_run.py"
    spec = importlib.util.spec_from_file_location("gemini_run_test", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPythonVersionGuard:
    def test_old_python_exits_with_clear_message(self) -> None:
        runner = _import_runner()
        with mock.patch("sys.version_info", (3, 8, 0)):
            with pytest.raises(SystemExit) as exc_info:
                runner._check_python_version()
            assert "3.9" in str(exc_info.value)

    def test_python_39_passes(self) -> None:
        runner = _import_runner()
        with mock.patch("sys.version_info", (3, 9, 0)):
            runner._check_python_version()  # must not raise

    def test_python_313_passes(self) -> None:
        runner = _import_runner()
        with mock.patch("sys.version_info", (3, 13, 0)):
            runner._check_python_version()


class TestVenvReExec:
    """``_maybe_reexec_under_venv`` swaps the interpreter when needed."""

    def test_no_op_when_already_in_venv(self, tmp_path: Path) -> None:
        runner = _import_runner()
        venv_python = tmp_path / "skill" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.touch()

        with mock.patch.object(runner, "_skill_venv_python", return_value=venv_python):
            with mock.patch("sys.executable", str(venv_python)):
                with mock.patch("os.execv") as mock_execv:
                    runner._maybe_reexec_under_venv()

        mock_execv.assert_not_called()

    def test_reexec_when_venv_exists_and_not_in_use(self, tmp_path: Path) -> None:
        runner = _import_runner()
        venv_python = tmp_path / "skill" / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.touch()

        with mock.patch.object(runner, "_skill_venv_python", return_value=venv_python):
            with mock.patch("sys.executable", "/usr/bin/python3"):
                with mock.patch("sys.argv", ["scripts/gemini_run.py", "text", "hi"]):
                    with mock.patch("os.execv") as mock_execv:
                        runner._maybe_reexec_under_venv()

        mock_execv.assert_called_once()
        called_path, called_argv = mock_execv.call_args.args
        assert called_path == str(venv_python)
        # The argv should start with the venv python so the re-exec'd
        # process knows its own interpreter.
        assert called_argv[0] == str(venv_python)
        # And the original argv tail must be preserved verbatim.
        assert called_argv[-2:] == ["text", "hi"]

    def test_no_op_when_venv_does_not_exist(self, tmp_path: Path) -> None:
        """Local-dev mode: no installed-skill venv, run the launcher
        unmodified so the repo-root .venv (or system Python) handles
        the dependencies."""
        runner = _import_runner()
        venv_python = tmp_path / "doesnt" / "exist" / "python"

        with mock.patch.object(runner, "_skill_venv_python", return_value=venv_python):
            with mock.patch("os.execv") as mock_execv:
                runner._maybe_reexec_under_venv()

        mock_execv.assert_not_called()


class TestSkillVenvPython:
    """The ``_skill_venv_python`` helper resolves the install path."""

    def test_returns_posix_path_on_unix(self) -> None:
        runner = _import_runner()
        with mock.patch("sys.platform", "darwin"):
            path = runner._skill_venv_python()
        assert path.parts[-3:] == (".venv", "bin", "python")

    def test_returns_windows_path_on_win32(self) -> None:
        runner = _import_runner()
        with mock.patch("sys.platform", "win32"):
            path = runner._skill_venv_python()
        assert path.parts[-3:] == (".venv", "Scripts", "python.exe")


class TestSysPathBootstrap:
    def test_ensure_repo_root_on_syspath_inserts_missing_root(self) -> None:
        runner = _import_runner()
        expected_root: str = runner._repo_root()

        with mock.patch.object(
            sys, "path", [entry for entry in sys.path if entry != expected_root]
        ):
            resolved_root: str = runner._ensure_repo_root_on_syspath()

            assert resolved_root == expected_root
            assert sys.path[0] == expected_root


class TestMainEntryPoint:
    """``main()`` orchestrates version check, venv re-exec, and dispatch."""

    def test_main_dispatches_to_core_cli_dispatch(self) -> None:
        """Smoke test: main() calls _check_python_version, skips re-exec
        (venv missing in tmp), then forwards argv to dispatch.main."""
        runner = _import_runner()
        with (
            mock.patch.object(runner, "_check_python_version") as mock_check,
            mock.patch.object(runner, "_bootstrap_runtime_environment") as mock_bootstrap,
            mock.patch.object(runner, "_maybe_reexec_under_venv") as mock_reexec,
            mock.patch("core.cli.dispatch.main", return_value=0) as mock_dispatch,
        ):
            runner.main(["text", "hello"])

        mock_check.assert_called_once()
        mock_bootstrap.assert_called_once()
        mock_reexec.assert_called_once()
        mock_dispatch.assert_called_once_with(["text", "hello"])

    def test_main_bootstraps_before_reexec(self) -> None:
        runner = _import_runner()
        call_order: list[str] = []

        def record_bootstrap() -> None:
            call_order.append("bootstrap")

        def record_reexec() -> None:
            call_order.append("reexec")

        with (
            mock.patch.object(runner, "_check_python_version"),
            mock.patch.object(
                runner, "_bootstrap_runtime_environment", side_effect=record_bootstrap
            ),
            mock.patch.object(runner, "_maybe_reexec_under_venv", side_effect=record_reexec),
            mock.patch("core.cli.dispatch.main", return_value=0),
        ):
            runner.main(["text", "hello"])

        assert call_order == ["bootstrap", "reexec"]


class TestBootstrapRuntimeEnvironment:
    def test_bootstrap_runtime_environment_exits_cleanly_on_resolution_error(self) -> None:
        runner = _import_runner()
        from core.infra.errors import EnvironmentResolutionError

        def raise_resolution_error() -> dict[str, str]:
            raise EnvironmentResolutionError("bad settings")

        with (
            mock.patch.object(runner, "_ensure_repo_root_on_syspath"),
            mock.patch(
                "core.infra.runtime_env.bootstrap_runtime_env",
                side_effect=raise_resolution_error,
            ),
        ):
            with pytest.raises(SystemExit, match="bad settings"):
                runner._bootstrap_runtime_environment()


class TestRunAsMain:
    """Exercises the ``if __name__ == '__main__'`` guard at the file bottom."""

    def test_run_path_triggers_main_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running the file via runpy with __main__ invokes main(argv[1:])."""
        import runpy

        script_path = Path(__file__).resolve().parents[2] / "scripts" / "gemini_run.py"
        fake_dispatch = mock.MagicMock(return_value=None)
        fake_dispatch_module = mock.MagicMock()
        fake_dispatch_module.main = fake_dispatch
        home_directory: Path = tmp_path / "home"
        home_directory.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(home_directory))

        with (
            mock.patch.dict(sys.modules, {"core.cli.dispatch": fake_dispatch_module}),
            mock.patch.object(sys, "argv", ["gemini_run.py", "text", "hi"]),
            # Skip the real venv re-exec check so we don't os.execv the test runner.
            mock.patch("pathlib.Path.exists", return_value=False),
        ):
            runpy.run_path(str(script_path), run_name="__main__")

        fake_dispatch.assert_called_once_with(["text", "hi"])
