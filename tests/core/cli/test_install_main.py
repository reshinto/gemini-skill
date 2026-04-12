"""Tests for core/cli/install_main.py."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _setup_fake_source(tmp_path: Path) -> Path:
    """Create a minimal fake source repo."""
    src = tmp_path / "source"
    src.mkdir()
    (src / "SKILL.md").write_text("# SKILL")
    (src / "VERSION").write_text("0.1.0")
    (src / ".env.example").write_text("GEMINI_API_KEY=\n")
    (src / "core").mkdir()
    (src / "core" / "__init__.py").write_text("")
    (src / "adapters").mkdir()
    (src / "adapters" / "__init__.py").write_text("")
    (src / "reference").mkdir()
    (src / "registry").mkdir()
    (src / "registry" / "models.json").write_text("{}")
    (src / "scripts").mkdir()
    (src / "scripts" / "gemini_run.py").write_text("# launcher")
    (src / "setup").mkdir()
    (src / "setup" / "update.py").write_text("# updater")
    return src


class TestInstallClean:
    def test_clean_install(self, tmp_path):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir):
            install_main.main([])

        assert (install_dir / "SKILL.md").exists()
        assert (install_dir / "VERSION").exists()
        assert (install_dir / "core" / "__init__.py").exists()
        assert (install_dir / "adapters" / "__init__.py").exists()
        assert (install_dir / "setup" / "update.py").exists()

    def test_creates_env_from_example(self, tmp_path):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir):
            install_main.main([])

        env_file = install_dir / ".env"
        assert env_file.exists()
        assert "GEMINI_API_KEY" in env_file.read_text()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
    def test_env_file_has_600_perms(self, tmp_path):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir):
            install_main.main([])

        env_file = install_dir / ".env"
        mode = stat.S_IMODE(env_file.stat().st_mode)
        assert mode == 0o600


class TestInstallReinstall:
    def test_overwrites_existing(self, tmp_path, capsys):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        (install_dir / "old_file").write_text("old")

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir), \
             patch.object(install_main, "_prompt", return_value="o"):
            install_main.main([])

        assert not (install_dir / "old_file").exists()
        assert (install_dir / "SKILL.md").exists()

    def test_skip_preserves_existing(self, tmp_path, capsys):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        (install_dir / "old_file").write_text("old")

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir), \
             patch.object(install_main, "_prompt", return_value="s"):
            install_main.main([])

        assert (install_dir / "old_file").exists()


class TestEnvMerge:
    def test_merge_adds_new_keys(self, tmp_path):
        from core.cli.install_main import _merge_env
        env = tmp_path / ".env"
        env.write_text("OLD_KEY=value\n")
        example = tmp_path / ".env.example"
        example.write_text("OLD_KEY=\nNEW_KEY=\n")

        _merge_env(env, example)
        content = env.read_text()
        assert "OLD_KEY=value" in content
        assert "NEW_KEY=" in content

    def test_merge_preserves_existing_values(self, tmp_path):
        from core.cli.install_main import _merge_env
        env = tmp_path / ".env"
        env.write_text("KEY=my-secret-value\n")
        example = tmp_path / ".env.example"
        example.write_text("KEY=\n")

        _merge_env(env, example)
        assert "my-secret-value" in env.read_text()

    def test_merge_no_changes_when_same(self, tmp_path):
        from core.cli.install_main import _merge_env
        env = tmp_path / ".env"
        env.write_text("KEY=value\n")
        example = tmp_path / ".env.example"
        example.write_text("KEY=\n")

        original = env.read_text()
        _merge_env(env, example)
        assert env.read_text() == original


class TestExtractKeys:
    def test_extracts_simple_keys(self):
        from core.cli.install_main import _extract_keys
        content = "KEY_A=value\nKEY_B=other\n"
        assert _extract_keys(content) == {"KEY_A", "KEY_B"}

    def test_skips_comments_and_blanks(self):
        from core.cli.install_main import _extract_keys
        content = "# comment\n\nKEY=value\n"
        assert _extract_keys(content) == {"KEY"}

    def test_skips_lines_without_equals(self):
        from core.cli.install_main import _extract_keys
        content = "no equals here\nKEY=value\n"
        assert _extract_keys(content) == {"KEY"}


class TestSourceAndInstallDir:
    def test_get_source_dir(self):
        from core.cli.install_main import _get_source_dir
        src = _get_source_dir()
        assert (src / "core").exists()

    def test_get_install_dir(self):
        from core.cli.install_main import _get_install_dir
        install_dir = _get_install_dir()
        assert ".claude/skills/gemini" in str(install_dir)


class TestEnvFileExists:
    def test_merges_when_env_already_exists(self, tmp_path):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"
        install_dir.mkdir(parents=True)
        (install_dir / ".env").write_text("OLD=value\n")

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir), \
             patch.object(install_main, "_prompt", return_value="s"):
            # Skip to avoid overwriting, but .env merge runs unconditionally
            # via a direct setup call
            install_main._setup_env_file(src, install_dir)

        content = (install_dir / ".env").read_text()
        assert "OLD=value" in content


class TestChmodFailures:
    def test_install_dir_chmod_failure(self, tmp_path, monkeypatch):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        original_chmod = os.chmod
        call_count = [0]

        def failing_chmod(path, mode, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("perm denied on dir")
            return original_chmod(path, mode, **kwargs)

        monkeypatch.setattr(os, "chmod", failing_chmod)

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir):
            install_main.main([])

        assert (install_dir / "SKILL.md").exists()

    def test_env_file_chmod_failure(self, tmp_path, monkeypatch):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        original_chmod = os.chmod
        calls = [0]

        def selective_chmod(path, mode, **kwargs):
            calls[0] += 1
            # Only fail on the .env chmod (second call or when mode == 0o600)
            if mode == 0o600:
                raise OSError("perm denied")
            return original_chmod(path, mode, **kwargs)

        monkeypatch.setattr(os, "chmod", selective_chmod)

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir):
            install_main.main([])

        assert (install_dir / ".env").exists()


class TestCleanInstallDirCollision:
    def test_existing_subdir_removed(self, tmp_path):
        from core.cli import install_main
        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        # Pre-existing core/ dir that must be replaced
        (install_dir / "core").mkdir()
        (install_dir / "core" / "old.py").write_text("old")

        install_main._clean_install(src, install_dir)
        assert not (install_dir / "core" / "old.py").exists()
        assert (install_dir / "core" / "__init__.py").exists()


class TestMergeEnvWithComments:
    def test_merge_skips_comment_lines_in_new_keys(self, tmp_path):
        from core.cli.install_main import _merge_env
        env = tmp_path / ".env"
        env.write_text("EXISTING=old\n")
        example = tmp_path / ".env.example"
        example.write_text(
            "# This is a comment\n"
            "EXISTING=\n"
            "\n"
            "NEW_KEY=\n"
            "# Another comment\n"
        )
        _merge_env(env, example)
        content = env.read_text()
        assert "NEW_KEY=" in content
        # Comments not copied
        assert "This is a comment" not in content


class TestPrompt:
    def test_prompt_wraps_input(self):
        from core.cli.install_main import _prompt
        with patch("builtins.input", return_value="user-response"):
            result = _prompt("Question: ")
        assert result == "user-response"


class TestInstallNoEnvExample:
    def test_no_env_example(self, tmp_path):
        from core.cli import install_main
        src = tmp_path / "source"
        src.mkdir()
        (src / "SKILL.md").write_text("# SKILL")
        (src / "VERSION").write_text("0.1.0")
        # no .env.example
        install_dir = tmp_path / "install"

        with patch.object(install_main, "_get_source_dir", return_value=src), \
             patch.object(install_main, "_get_install_dir", return_value=install_dir):
            install_main.main([])

        assert (install_dir / "SKILL.md").exists()
        assert not (install_dir / ".env").exists()
