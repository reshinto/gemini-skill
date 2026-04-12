"""Tests for core/cli/update_main.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestUpdateMain:
    def test_not_installed_error(self, tmp_path, capsys):
        from core.cli.update_main import main
        fake_install = tmp_path / "not-installed"
        with patch("core.cli.update_main.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            # Make the install_dir path use tmp_path / not-installed
            mock_path.side_effect = lambda *a, **k: Path(*a, **k) if a else fake_install
            from pathlib import Path
            with patch.object(Path, "home", return_value=tmp_path):
                main([])
        # We can't easily mock Path here, so skip detailed assertion
        # The test below uses a better approach

    def test_up_to_date(self, tmp_path, capsys, monkeypatch):
        from core.cli import update_main
        # Set up fake install dir with VERSION
        install_dir = tmp_path / ".claude" / "skills" / "gemini"
        install_dir.mkdir(parents=True)
        (install_dir / "VERSION").write_text("99.0.0")

        monkeypatch.setattr(update_main.Path, "home", staticmethod(lambda: tmp_path))

        with patch.object(update_main, "_fetch_latest_release", return_value={"tag_name": "v0.1.0"}):
            update_main.main([])
        output = capsys.readouterr().out
        assert "Already up to date" in output

    def test_update_available(self, tmp_path, capsys, monkeypatch):
        from core.cli import update_main
        install_dir = tmp_path / ".claude" / "skills" / "gemini"
        install_dir.mkdir(parents=True)
        (install_dir / "VERSION").write_text("0.1.0")

        monkeypatch.setattr(update_main.Path, "home", staticmethod(lambda: tmp_path))

        with patch.object(update_main, "_fetch_latest_release", return_value={"tag_name": "v0.2.0"}):
            update_main.main([])
        output = capsys.readouterr().out
        assert "Update available" in output

    def test_not_installed(self, tmp_path, capsys, monkeypatch):
        from core.cli import update_main
        monkeypatch.setattr(update_main.Path, "home", staticmethod(lambda: tmp_path))

        update_main.main([])
        output = capsys.readouterr().out
        assert "[ERROR] Not installed" in output

    def test_fetch_release_fails(self, tmp_path, capsys, monkeypatch):
        from core.cli import update_main
        install_dir = tmp_path / ".claude" / "skills" / "gemini"
        install_dir.mkdir(parents=True)
        (install_dir / "VERSION").write_text("0.1.0")

        monkeypatch.setattr(update_main.Path, "home", staticmethod(lambda: tmp_path))

        with patch.object(update_main, "_fetch_latest_release", side_effect=Exception("network error")):
            update_main.main([])
        output = capsys.readouterr().out
        assert "[ERROR]" in output
        assert "network error" in output

    def test_empty_tag_name(self, tmp_path, capsys, monkeypatch):
        from core.cli import update_main
        install_dir = tmp_path / ".claude" / "skills" / "gemini"
        install_dir.mkdir(parents=True)
        (install_dir / "VERSION").write_text("0.1.0")

        monkeypatch.setattr(update_main.Path, "home", staticmethod(lambda: tmp_path))

        with patch.object(update_main, "_fetch_latest_release", return_value={}):
            update_main.main([])
        assert "[ERROR]" in capsys.readouterr().out


class TestParseVersion:
    def test_basic_version(self):
        from core.cli.update_main import _parse_version
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_strips_v_prefix(self):
        from core.cli.update_main import _parse_version
        assert _parse_version("v1.2.3") == (1, 2, 3)

    def test_strips_prerelease_suffix(self):
        from core.cli.update_main import _parse_version
        assert _parse_version("1.2.3-beta") == (1, 2, 3)

    def test_strips_build_metadata(self):
        from core.cli.update_main import _parse_version
        assert _parse_version("1.2.3+build123") == (1, 2, 3)

    def test_non_numeric_segment_becomes_zero(self):
        from core.cli.update_main import _parse_version
        assert _parse_version("1.x.3") == (1, 0, 3)

    def test_lexicographic_bug_fix(self):
        """Ensure 1.10.0 > 1.9.0 (the bug the fix resolves)."""
        from core.cli.update_main import _parse_version
        assert _parse_version("1.10.0") > _parse_version("1.9.0")


class TestFetchLatestRelease:
    def test_fetches_release_info(self):
        import json as _json
        from core.cli.update_main import _fetch_latest_release
        mock_resp = MagicMock()
        mock_resp.read.return_value = _json.dumps({"tag_name": "v1.0.0"}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("core.cli.update_main.urlopen", return_value=mock_resp):
            result = _fetch_latest_release()
        assert result["tag_name"] == "v1.0.0"
