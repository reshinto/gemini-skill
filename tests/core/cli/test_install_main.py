"""Tests for core/cli/install_main.py."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_home_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_directory: Path = tmp_path / "home"
    (home_directory / ".claude").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_directory))


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

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
        ):
            install_main.main([])

        assert (install_dir / "SKILL.md").exists()
        assert (install_dir / "VERSION").exists()
        assert (install_dir / "core" / "__init__.py").exists()
        assert (install_dir / "adapters" / "__init__.py").exists()
        assert (install_dir / "setup" / "update.py").exists()

    def test_creates_settings_json_with_env_keys(self, tmp_path, monkeypatch):
        """Phase 5: install writes env vars into ~/.claude/settings.json
        instead of a skill-local .env file. Assert the new contract."""
        import json
        from core.cli import install_main

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home" / ".claude").mkdir(parents=True, exist_ok=True)

        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_is_interactive_stdin", return_value=False),
        ):
            install_main.main([])

        settings_path = tmp_path / "home" / ".claude" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        assert "GEMINI_API_KEY" in data["env"]
        # The skill-local .env file is NO LONGER created.
        assert not (install_dir / ".env").exists()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
    def test_settings_json_has_600_perms(self, tmp_path, monkeypatch):
        """Phase 5: the settings.json atomic write sets 0o600 perms
        via core/infra/atomic_write.py. Pin the permission contract."""
        from core.cli import install_main

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home" / ".claude").mkdir(parents=True, exist_ok=True)

        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_is_interactive_stdin", return_value=False),
        ):
            install_main.main([])

        settings_path = tmp_path / "home" / ".claude" / "settings.json"
        mode = stat.S_IMODE(settings_path.stat().st_mode)
        assert mode == 0o600


class TestInstallReinstall:
    def test_overwrites_existing(self, tmp_path, capsys):
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        (install_dir / "old_file").write_text("old")

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_prompt", return_value="o"),
        ):
            install_main.main([])

        assert not (install_dir / "old_file").exists()
        assert (install_dir / "SKILL.md").exists()

    def test_skip_preserves_existing(self, tmp_path, capsys):
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        (install_dir / "old_file").write_text("old")

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_prompt", return_value="s"),
        ):
            install_main.main([])

        assert (install_dir / "old_file").exists()


# NOTE: TestEnvMerge and TestExtractKeys were removed in the Phase 5
# follow-up slice. The ``_setup_env_file`` / ``_merge_env`` /
# ``_extract_keys`` helpers were deleted along with the tests because
# the skill-local .env file is deprecated — env vars now live in
# ~/.claude/settings.json via core/cli/installer/settings_merge.py.


class TestSourceAndInstallDir:
    def test_get_source_dir(self):
        from core.cli.install_main import _get_source_dir

        src = _get_source_dir()
        assert (src / "core").exists()

    def test_get_install_dir(self):
        from core.cli.install_main import _get_install_dir

        install_dir = _get_install_dir()
        assert ".claude/skills/gemini" in str(install_dir)


# TestEnvFileExists removed — _setup_env_file deleted along with
# every other skill-local .env helper in the Phase 5 follow-up.


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

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
        ):
            install_main.main([])

        assert (install_dir / "SKILL.md").exists()

    def test_settings_chmod_failure_is_tolerated(self, tmp_path, monkeypatch):
        """Phase 5: the settings.json write goes through
        core/infra/atomic_write.py which swallows chmod failures
        (some filesystems don't support POSIX perms). The install
        must still complete successfully even when chmod raises."""
        from core.cli import install_main

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home" / ".claude").mkdir(parents=True, exist_ok=True)

        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        original_chmod = os.chmod

        def selective_chmod(path, mode, **kwargs):
            # Fail only on 0o600 (file chmod) — allow 0o700 (dir chmod).
            if mode == 0o600:
                raise OSError("perm denied")
            return original_chmod(path, mode, **kwargs)

        monkeypatch.setattr(os, "chmod", selective_chmod)

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_is_interactive_stdin", return_value=False),
        ):
            install_main.main([])

        settings_path = tmp_path / "home" / ".claude" / "settings.json"
        assert settings_path.exists()


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


# TestMergeEnvWithComments removed — see note above TestSourceAndInstallDir.


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

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
        ):
            install_main.main([])

        assert (install_dir / "SKILL.md").exists()
        assert not (install_dir / ".env").exists()


class TestVenvWiring:
    """Phase 5: install_main must orchestrate venv creation + pip install
    + SDK probe via the core/cli/installer/venv.py helpers.

    Three contracts:
    1. Venv is created at ``<install_dir>/.venv``.
    2. ``setup/requirements.txt`` is installed into that venv.
    3. The SDK is verified importable from inside the venv.

    All three calls are mocked so tests don't touch the real network or
    create actual venvs (which would balloon test runtime to seconds).
    """

    def test_install_creates_venv_after_copying_files(self, tmp_path):
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        # Add a setup/requirements.txt to the fake source so the
        # installer has something to point pip at.
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv") as mock_create,
            patch("core.cli.installer.venv.install_requirements") as mock_install_req,
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
        ):
            install_main.main([])

        # Venv created at the expected path.
        mock_create.assert_called_once()
        venv_target = mock_create.call_args.args[0]
        assert venv_target == install_dir / ".venv"

        # pip install was called against the same venv with the
        # requirements file from the install dir (NOT the source dir,
        # because the file was just copied as part of _OPERATIONAL_DIRS).
        mock_install_req.assert_called_once()
        req_call_args = mock_install_req.call_args.args
        assert req_call_args[0] == install_dir / ".venv"

    def test_install_verifies_sdk_after_pip_install(self, tmp_path):
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch(
                "core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"
            ) as mock_verify,
        ):
            install_main.main([])

        mock_verify.assert_called_once_with(install_dir / ".venv")

    def test_venv_failure_does_not_abort_install(self, tmp_path, capsys):
        """If venv creation or pip install fails, the installer should
        warn loudly but leave the file copy intact — the user can
        re-run install once the venv issue is resolved, and the
        existing raw HTTP backend still works without google-genai."""
        from core.cli import install_main
        from core.cli.installer.venv import InstallError

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv"),
            patch(
                "core.cli.installer.venv.install_requirements",
                side_effect=InstallError("pip exit 1"),
            ),
        ):
            install_main.main([])

        # File copy still happened.
        assert (install_dir / "SKILL.md").exists()
        # Warning was surfaced to the user.
        captured = capsys.readouterr()
        assert "venv" in captured.out.lower() or "sdk" in captured.out.lower()
        assert "pip exit 1" in captured.out or "raw HTTP" in captured.out

    def test_install_prints_sdk_version_summary(self, tmp_path, capsys):
        """End-of-install summary must include the installed SDK version
        so users see what they got."""
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
        ):
            install_main.main([])

        captured = capsys.readouterr()
        assert "1.33.0" in captured.out

    def test_install_skips_venv_when_no_requirements_file(self, tmp_path):
        """If the source repo does not ship a setup/requirements.txt
        (e.g. a stripped-down test fixture), the installer should
        skip the venv step entirely rather than pretending to install."""
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        # No requirements.txt — _setup_fake_source does NOT create one
        # by default.
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv") as mock_create,
        ):
            install_main.main([])

        mock_create.assert_not_called()


class TestVenvPreservation:
    """On overwrite, the existing ``.venv`` directory must be preserved
    so re-running install (e.g. to update files after a git pull) is
    a fast no-op for the venv step instead of a multi-second rebuild.

    The contract: file copy nukes everything EXCEPT ``.venv``. The
    venv installer then re-runs ``install_requirements`` against the
    preserved venv, which is a no-op when the pinned version is
    already installed (no --upgrade flag).
    """

    def test_overwrite_preserves_existing_venv(self, tmp_path):
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        # Pre-create an "existing install" with a venv directory
        # holding a marker file. After overwrite, the marker must
        # still be there.
        install_dir.mkdir()
        (install_dir / "SKILL.md").write_text("# old version")
        (install_dir / ".venv").mkdir()
        (install_dir / ".venv" / "marker").write_text("preserved")

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_prompt", return_value="o"),
            patch("core.cli.installer.venv.create_venv") as mock_create,
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
        ):
            install_main.main([])

        # The .venv marker must still exist after overwrite.
        assert (install_dir / ".venv" / "marker").exists()
        assert (install_dir / ".venv" / "marker").read_text() == "preserved"
        # And create_venv should NOT have been called — the existing
        # venv was preserved, no rebuild needed.
        mock_create.assert_not_called()
        # SKILL.md should be the new content from the fresh source.
        assert (install_dir / "SKILL.md").read_text() == "# SKILL"

    def test_fresh_install_creates_venv(self, tmp_path):
        """Sanity: a fresh install with no pre-existing venv DOES
        create one. Pin the contract in the other direction."""
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv") as mock_create,
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
        ):
            install_main.main([])

        mock_create.assert_called_once()

    def test_overwrite_removes_subdirectory_entries(self, tmp_path):
        """Coverage for the directory branch of _clean_install_dir_preserve_venv:
        overwrite an install where the existing dir contains both files
        AND subdirectories — both must be removed, .venv must stay."""
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        (install_dir / "SKILL.md").write_text("old")
        # A pre-existing subdirectory that's NOT .venv — must be removed.
        (install_dir / "old_subdir").mkdir()
        (install_dir / "old_subdir" / "stale.py").write_text("# stale")
        # The venv directory — must be preserved.
        (install_dir / ".venv").mkdir()
        (install_dir / ".venv" / "marker").write_text("keep")

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_prompt", return_value="o"),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
        ):
            install_main.main([])

        # The stale subdir must be gone (rmtree branch).
        assert not (install_dir / "old_subdir").exists()
        # The venv must still be there.
        assert (install_dir / ".venv" / "marker").read_text() == "keep"


class TestSettingsBufferFiltering:
    def test_non_dict_buffer_env_produces_empty_pre_resolved(self, tmp_path):
        from core.cli import install_main

        install_dir: Path = tmp_path / "install"
        install_dir.mkdir()

        def seed_non_dict_env(
            legacy_env_path: Path,
            settings_buffer: dict[str, object],
            *,
            yes: bool,
            interactive: bool,
        ) -> None:
            del legacy_env_path
            del yes
            del interactive
            settings_buffer["env"] = ["unexpected"]

        with (
            patch("core.cli.install_main.migrate_legacy_env_to_settings", side_effect=seed_non_dict_env),
            patch("core.cli.install_main.prompt_gemini_api_key"),
            patch("core.cli.install_main.merge_settings_env") as mock_merge_settings_env,
        ):
            install_main._setup_user_settings(install_dir, yes=False, interactive=False)

        assert mock_merge_settings_env.call_args.kwargs["pre_resolved"] == {}

    def test_non_string_buffer_entries_are_filtered(self, tmp_path):
        from core.cli import install_main

        install_dir: Path = tmp_path / "install"
        install_dir.mkdir()

        def seed_mixed_env(
            legacy_env_path: Path,
            settings_buffer: dict[str, object],
            *,
            yes: bool,
            interactive: bool,
        ) -> None:
            del legacy_env_path
            del yes
            del interactive
            settings_buffer["env"] = {
                "GEMINI_API_KEY": "key",
                "GEMINI_LIVE_TESTS": 1,
                3: "ignored",
            }

        with (
            patch("core.cli.install_main.migrate_legacy_env_to_settings", side_effect=seed_mixed_env),
            patch("core.cli.install_main.prompt_gemini_api_key"),
            patch("core.cli.install_main.merge_settings_env") as mock_merge_settings_env,
        ):
            install_main._setup_user_settings(install_dir, yes=False, interactive=False)

        assert mock_merge_settings_env.call_args.kwargs["pre_resolved"] == {
            "GEMINI_API_KEY": "key"
        }


class TestManifestCoverage:
    def test_manifest_write_failure_is_warned_and_install_continues(self, tmp_path, capsys):
        from core.cli import install_main

        src = _setup_fake_source(tmp_path)
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_write_install_manifest", side_effect=OSError("disk full")),
            patch.object(install_main, "_setup_user_settings"),
        ):
            install_main.main([])

        captured = capsys.readouterr()
        assert "Install manifest write failed" in captured.out
        assert (install_dir / "SKILL.md").exists()

    def test_iter_manifest_files_skips_checksums_file(self, tmp_path):
        from core.cli.install_main import _iter_manifest_files

        install_dir: Path = tmp_path / "install"
        install_dir.mkdir()
        (install_dir / ".checksums.json").write_text("{}")
        kept_file: Path = install_dir / "SKILL.md"
        kept_file.write_text("# skill")

        manifest_files: list[Path] = _iter_manifest_files(install_dir)

        assert manifest_files == [kept_file]

    def test_verify_install_integrity_returns_empty_without_manifest(self, tmp_path):
        from core.cli.install_main import verify_install_integrity

        install_dir: Path = tmp_path / "install"
        install_dir.mkdir()

        assert verify_install_integrity(install_dir) == []

    def test_verify_install_integrity_reads_existing_manifest(self, tmp_path):
        from core.cli import install_main

        install_dir: Path = tmp_path / "install"
        install_dir.mkdir()
        manifest_path: Path = install_dir / ".checksums.json"
        manifest_path.write_text("{}")

        with (
            patch("core.cli.install_main.read_checksums_file", return_value={"SKILL.md": "abc"}) as mock_read,
            patch("core.cli.install_main.verify_checksums", return_value=["SKILL.md"]) as mock_verify,
        ):
            mismatches: list[str] = install_main.verify_install_integrity(install_dir)

        mock_read.assert_called_once_with(manifest_path)
        mock_verify.assert_called_once_with(install_dir, {"SKILL.md": "abc"})
        assert mismatches == ["SKILL.md"]


# TestOverlayBufferOnSettings removed — the Phase 5 squash review
# collapsed the two-step merge + overlay design into a single
# atomic write via the ``pre_resolved`` kwarg on merge_settings_env.
# The overlay helper no longer exists.


class TestSettingsJsonWiring:
    """Phase 5 follow-up: install_main calls api_key_prompt +
    merge_settings_env + migrate_legacy_env_to_settings in the
    correct order with a real tmp settings.json path."""

    def test_settings_merge_runs_after_venv_setup(self, tmp_path, monkeypatch):
        """End-to-end: install into tmp_path with a tmp HOME so we
        never touch the real ~/.claude/settings.json. Assert the
        merge helpers produced a file with the default keys."""
        import json
        from core.cli import install_main

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home" / ".claude").mkdir(parents=True, exist_ok=True)

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
            patch.object(install_main, "_is_interactive_stdin", return_value=False),
        ):
            # yes=False but non-interactive stdin → auto-skip prompts.
            install_main.main([])

        settings_path = tmp_path / "home" / ".claude" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        # Every default key must be present in env.
        assert "env" in data
        assert "GEMINI_API_KEY" in data["env"]
        assert data["env"]["GEMINI_IS_SDK_PRIORITY"] == "true"
        assert data["env"]["GEMINI_IS_RAWHTTP_PRIORITY"] == "false"
        assert data["env"]["GEMINI_LIVE_TESTS"] == "0"

    def test_malformed_settings_json_raises_hard(self, tmp_path, monkeypatch, capsys):
        """A malformed ~/.claude/settings.json causes the install to
        abort — SettingsFileCorrupted is re-raised from
        ``_setup_user_settings`` so the user's corrupted file is
        never silently tolerated. File copy stays intact (happened
        before the error)."""
        from core.cli import install_main
        from core.cli.installer.settings_merge import SettingsFileCorrupted

        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        (home / ".claude").mkdir(parents=True, exist_ok=True)
        (home / ".claude" / "settings.json").write_text("not json {")

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
            patch.object(install_main, "_is_interactive_stdin", return_value=False),
        ):
            with pytest.raises(SettingsFileCorrupted):
                install_main.main([])

        captured = capsys.readouterr()
        assert "[ERROR]" in captured.out
        assert "settings.json" in captured.out
        # File copy still happened before the error bubbled up.
        assert (install_dir / "SKILL.md").exists()

    def test_generic_install_error_is_demoted_to_warn(self, tmp_path, monkeypatch, capsys):
        """A non-abort, non-corrupted InstallError (e.g. a helper
        raising because of an unexpected edge case) is caught by the
        generic except clause and demoted to a [WARN] line so the
        rest of the install still completes."""
        from core.cli import install_main
        from core.cli.installer.venv import InstallError

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home" / ".claude").mkdir(parents=True, exist_ok=True)

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        # Force merge_settings_env to raise a plain InstallError that
        # is neither SettingsFileCorrupted nor InstallAborted — that
        # takes the catch-all branch.
        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
            patch.object(install_main, "_is_interactive_stdin", return_value=False),
            patch(
                "core.cli.install_main.merge_settings_env",
                side_effect=InstallError("unexpected edge case"),
            ),
        ):
            install_main.main([])

        captured = capsys.readouterr()
        assert "[WARN]" in captured.out
        assert "unexpected edge case" in captured.out
        # File copy still completed.
        assert (install_dir / "SKILL.md").exists()

    def test_user_quit_during_prompt_raises_hard(self, tmp_path, monkeypatch, capsys):
        """If the user chooses ``q`` during a conflict prompt, the
        install exits non-zero. The quit must NOT be demoted to a
        warning."""
        import json as _json
        from core.cli import install_main
        from core.cli.installer.settings_merge import InstallAborted

        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        (home / ".claude").mkdir(parents=True, exist_ok=True)
        # Pre-existing settings.json with a conflict so the prompt fires.
        (home / ".claude" / "settings.json").write_text(
            _json.dumps({"env": {"GEMINI_IS_SDK_PRIORITY": "false"}})
        )

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = tmp_path / "install"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
            patch.object(install_main, "_is_interactive_stdin", return_value=True),
            # The API-key prompt runs before the generic merge. Leave
            # the key empty so it doesn't matter, then script the
            # input() calls: the first is the u/k choice (absent-key
            # path skips this), getpass returns empty, and then the
            # conflict prompt for GEMINI_IS_SDK_PRIORITY gets "q".
            patch("getpass.getpass", return_value=""),
            patch("builtins.input", return_value="q"),
        ):
            with pytest.raises(InstallAborted):
                install_main.main([])

        captured = capsys.readouterr()
        assert "[ABORT]" in captured.out

    def test_legacy_env_is_migrated(self, tmp_path, monkeypatch):
        """If a legacy ~/.claude/skills/gemini/.env exists at install
        time, its values are merged into settings.json and the file
        is offered for deletion (auto-deleted in non-interactive)."""
        import json
        from core.cli import install_main

        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        (home / ".claude" / "skills" / "gemini").mkdir(parents=True, exist_ok=True)
        legacy_env = home / ".claude" / "skills" / "gemini" / ".env"
        legacy_env.write_text("GEMINI_LIVE_TESTS=1\n")

        src = _setup_fake_source(tmp_path)
        (src / "setup" / "requirements.txt").write_text("google-genai==1.33.0\n")
        install_dir = home / ".claude" / "skills" / "gemini"

        with (
            patch.object(install_main, "_get_source_dir", return_value=src),
            patch.object(install_main, "_get_install_dir", return_value=install_dir),
            patch.object(install_main, "_prompt", return_value="o"),
            patch("core.cli.installer.venv.create_venv"),
            patch("core.cli.installer.venv.install_requirements"),
            patch("core.cli.installer.venv.verify_sdk_importable", return_value="1.33.0"),
            patch.object(install_main, "_is_interactive_stdin", return_value=False),
        ):
            install_main.main([])

        # The legacy value was picked up by the migration and stored
        # in settings.json env.
        settings_path = home / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text())
        assert data["env"]["GEMINI_LIVE_TESTS"] == "1"
        # The legacy file was auto-deleted (non-interactive mode).
        assert not legacy_env.exists()
