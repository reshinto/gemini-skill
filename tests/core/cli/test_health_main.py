"""Tests for core/cli/health_main.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestHealthMain:
    def test_all_checks_pass(self, capsys):
        from core.cli.health_main import main

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": [{"name": "m1"}]}),
        ):
            main([])
        output = capsys.readouterr().out
        assert "[OK] API key resolved" in output
        assert "[OK] API reachable" in output
        assert "All checks passed" in output

    def test_auth_failure(self, capsys):
        from core.cli.health_main import main
        from core.infra.errors import AuthError

        with patch("core.auth.auth.resolve_key", side_effect=AuthError("no key")):
            main([])
        output = capsys.readouterr().out
        assert "[FAIL] API key" in output
        assert "All checks passed" not in output

    def test_api_connectivity_failure(self, capsys):
        from core.cli.health_main import main

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", side_effect=Exception("network down")),
        ):
            main([])
        output = capsys.readouterr().out
        assert "[FAIL] API connectivity" in output
        assert "All checks passed" not in output


class TestBackendReporting:
    """Phase 5: ``health`` reports backend selection + venv state.

    The user runs `gemini health` to confirm the dual-backend stack is
    wired up correctly. The output must surface, in order:
    - which backend is primary (per current Config flags)
    - which backend is the fallback (or "(none)")
    - whether the skill venv exists, and its path
    - the pinned google-genai version (from setup/requirements.txt)
    - the installed google-genai version (from the venv probe)
    - a WARN line if pinned and installed drift apart
    """

    def test_reports_primary_and_fallback_backend(self, capsys, tmp_path):
        from core.cli.health_main import main

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
        ):
            main([])

        output = capsys.readouterr().out
        # By default Config.is_sdk_priority=True, is_rawhttp_priority=False
        # → primary=sdk, fallback=None
        assert "Primary backend: sdk" in output
        assert "Fallback backend: " in output  # "(none)" or "raw_http"

    def test_reports_venv_path_and_existence(self, capsys, tmp_path):
        from core.cli.health_main import main

        # Simulate an installed venv inside tmp_path so the path-exists
        # branch is exercised.
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
        ):
            main([])

        output = capsys.readouterr().out
        assert "Venv:" in output
        assert "exists" in output

    def test_reports_venv_missing(self, capsys, tmp_path):
        from core.cli.health_main import main

        # No .venv directory under the install dir.
        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
        ):
            main([])

        output = capsys.readouterr().out
        assert "Venv:" in output
        assert "missing" in output

    def test_reports_pinned_and_installed_sdk_versions(self, capsys, tmp_path):
        from core.cli.health_main import main

        # Set up a fake install dir with setup/requirements.txt + .venv.
        (tmp_path / "setup").mkdir()
        (tmp_path / "setup" / "requirements.txt").write_text("# pin\ngoogle-genai==1.33.0\n")
        (tmp_path / ".venv").mkdir()

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
        ):
            main([])

        output = capsys.readouterr().out
        assert "google-genai" in output
        assert "pinned=1.33.0" in output
        assert "installed=1.33.0" in output

    def test_warns_on_sdk_version_drift(self, capsys, tmp_path):
        """If pinned and installed differ, surface a WARN line so
        users notice when they've bypassed the install flow with an
        out-of-band ``pip install --upgrade``."""
        from core.cli.health_main import main

        (tmp_path / "setup").mkdir()
        (tmp_path / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        (tmp_path / ".venv").mkdir()

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.34.0"),
        ):
            main([])

        output = capsys.readouterr().out
        assert "WARN" in output or "drift" in output.lower()

    def test_no_drift_warning_when_versions_match(self, capsys, tmp_path):
        from core.cli.health_main import main

        (tmp_path / "setup").mkdir()
        (tmp_path / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        (tmp_path / ".venv").mkdir()

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
        ):
            main([])

        output = capsys.readouterr().out
        assert "WARN" not in output
        assert "SDK version drift" not in output

    def test_handles_missing_requirements_file_gracefully(self, capsys, tmp_path):
        """If the install dir has no setup/requirements.txt (e.g. a
        legacy install from before Phase 5), report 'unknown' instead
        of crashing."""
        from core.cli.health_main import main

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
        ):
            main([])

        output = capsys.readouterr().out
        # Should not crash; should report SOMETHING about the missing pin.
        assert "google-genai" in output

    def test_handles_requirements_file_without_google_genai_pin(self, capsys, tmp_path):
        """A requirements.txt that exists but doesn't pin google-genai
        (e.g. a hand-edited file with the pin commented out) must
        report ``unknown`` instead of crashing on a None match.
        Exercises the regex non-match branch of _read_pinned_version."""
        from core.cli.health_main import main

        (tmp_path / "setup").mkdir()
        (tmp_path / "setup" / "requirements.txt").write_text(
            "# google-genai==1.33.0  (commented out)\nrequests==2.31.0\n"
        )

        with (
            patch("core.auth.auth.resolve_key", return_value="fake-key"),
            patch("core.infra.client.api_call", return_value={"models": []}),
            patch("core.cli.health_main._install_dir", return_value=tmp_path),
        ):
            main([])

        output = capsys.readouterr().out
        assert "pinned=unknown" in output
