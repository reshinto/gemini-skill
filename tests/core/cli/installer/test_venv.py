"""Tests for core/cli/installer/venv.py — skill-local venv creation.

The venv module is the piece of Phase 5 that turns "files copied to
~/.claude/skills/gemini" into "a working installation that can run
google-genai". Three responsibilities:

1. Create a Python venv at ``<install_dir>/.venv`` via ``venv.EnvBuilder``.
2. Install the pinned runtime dependencies from ``setup/requirements.txt``
   into that venv via ``<venv>/bin/python -m pip install -r ...``.
3. Verify the venv can ``import google.genai`` AND that the import
   resolved from inside the venv (defense in depth against a bug that
   accidentally pip-installs to the system python).

The module is pure orchestration over stdlib ``venv`` + ``subprocess``,
so the unit tests mock ``EnvBuilder`` and ``subprocess.run`` to assert
the right calls happen in the right order. No real venv is created.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest


class TestVenvPythonPath:
    """The resolved python-binary path inside a venv differs by OS."""

    def test_posix_python_path(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import venv_python_path

        with mock.patch("sys.platform", "darwin"):
            assert venv_python_path(tmp_path) == tmp_path / "bin" / "python"

    def test_linux_python_path(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import venv_python_path

        with mock.patch("sys.platform", "linux"):
            assert venv_python_path(tmp_path) == tmp_path / "bin" / "python"

    def test_windows_python_path(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import venv_python_path

        with mock.patch("sys.platform", "win32"):
            assert venv_python_path(tmp_path) == tmp_path / "Scripts" / "python.exe"


class TestCreateVenv:
    """``create_venv`` builds a virtual environment via stdlib ``venv``."""

    def test_creates_venv_at_target_path(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import create_venv

        target = tmp_path / "skill" / ".venv"
        with mock.patch("core.cli.installer.venv.venv.EnvBuilder") as MockBuilder:
            mock_instance = mock.Mock()
            MockBuilder.return_value = mock_instance
            create_venv(target)

        # EnvBuilder must be constructed with pip enabled so the venv
        # can install the runtime dependency without an extra step.
        MockBuilder.assert_called_once()
        kwargs = MockBuilder.call_args.kwargs
        assert kwargs.get("with_pip") is True
        # And the create() call must point at the target path.
        mock_instance.create.assert_called_once_with(str(target))

    def test_creates_parent_directory_if_missing(self, tmp_path: Path) -> None:
        """The skill install dir is the parent of .venv. The installer
        flow already creates that, but the venv helper should not
        crash if the parent is missing — a fresh install on a new
        machine has no parent yet at the moment this runs."""
        from core.cli.installer.venv import create_venv

        target = tmp_path / "fresh" / "skill" / ".venv"
        with mock.patch("core.cli.installer.venv.venv.EnvBuilder") as MockBuilder:
            mock_instance = mock.Mock()
            MockBuilder.return_value = mock_instance
            create_venv(target)

        assert target.parent.exists()


class TestInstallRequirements:
    """``install_requirements`` invokes pip inside the venv."""

    def test_calls_venv_python_with_pip_install(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import install_requirements

        venv_dir = tmp_path / ".venv"
        req = tmp_path / "requirements.txt"
        req.write_text("google-genai==1.33.0\n")

        with mock.patch("core.cli.installer.venv.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            install_requirements(venv_dir, req)

        # Exactly one pip-install invocation.
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args.args[0] if call_args.args else call_args.kwargs.get("args", [])
        assert "pip" in cmd
        assert "install" in cmd
        assert "-r" in cmd
        assert str(req) in cmd
        # IMPORTANT: it must be the venv's python, NOT sys.executable.
        # Otherwise pip installs into system Python, defeating isolation.
        assert (
            str(venv_dir / "bin" / "python") in cmd
            or str(venv_dir / "Scripts" / "python.exe") in cmd
        )

    def test_no_upgrade_flag(self, tmp_path: Path) -> None:
        """Pinned-version contract: pip must NOT receive --upgrade.
        Re-running install on an existing venv should be a no-op when
        the pinned version is already present."""
        from core.cli.installer.venv import install_requirements

        venv_dir = tmp_path / ".venv"
        req = tmp_path / "requirements.txt"
        req.write_text("google-genai==1.33.0\n")

        with mock.patch("core.cli.installer.venv.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0)
            install_requirements(venv_dir, req)

        cmd = mock_run.call_args.args[0]
        assert "--upgrade" not in cmd
        assert "-U" not in cmd

    def test_pip_failure_raises_install_error(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import InstallError, install_requirements

        venv_dir = tmp_path / ".venv"
        req = tmp_path / "requirements.txt"
        req.write_text("google-genai==1.33.0\n")

        with mock.patch("core.cli.installer.venv.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="pip resolver error")
            with pytest.raises(InstallError, match="pip install failed"):
                install_requirements(venv_dir, req)

    def test_missing_requirements_file_raises(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import InstallError, install_requirements

        venv_dir = tmp_path / ".venv"
        with pytest.raises(InstallError, match="requirements file not found"):
            install_requirements(venv_dir, tmp_path / "missing.txt")


class TestVerifySdkImportable:
    """``verify_sdk_importable`` runs the venv python to assert the SDK loads."""

    def test_returns_version_on_success(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import verify_sdk_importable

        venv_dir = tmp_path / ".venv"
        with mock.patch("core.cli.installer.venv.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="1.33.0\n", stderr="")
            version = verify_sdk_importable(venv_dir)

        assert version == "1.33.0"
        # The probe runs the venv python with `-c "import google.genai;
        # print(google.genai.__version__)"`. Verify the venv python
        # binary is what's invoked.
        call_args = mock_run.call_args
        cmd = call_args.args[0]
        assert any("python" in str(c) for c in cmd)
        assert "-c" in cmd

    def test_import_failure_raises_install_error(self, tmp_path: Path) -> None:
        from core.cli.installer.venv import InstallError, verify_sdk_importable

        venv_dir = tmp_path / ".venv"
        with mock.patch("core.cli.installer.venv.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="ModuleNotFoundError: google.genai"
            )
            with pytest.raises(InstallError, match="SDK not importable"):
                verify_sdk_importable(venv_dir)

    def test_probe_asserts_import_resolved_from_inside_venv(self, tmp_path: Path) -> None:
        """Defense in depth: the probe code must include an assertion
        that ``sys.executable`` (inside the venv subprocess) lives
        under the venv path. Otherwise a buggy venv setup that fell
        back to system Python would silently report success."""
        from core.cli.installer.venv import verify_sdk_importable

        venv_dir = tmp_path / ".venv"
        with mock.patch("core.cli.installer.venv.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="1.33.0\n")
            verify_sdk_importable(venv_dir)

        # The probe code is the last positional element after `-c`.
        cmd = mock_run.call_args.args[0]
        c_index = cmd.index("-c")
        probe_code = cmd[c_index + 1]
        assert "sys.executable" in probe_code
        assert ".venv" in probe_code
