"""Tests for core/cli/installer/legacy_migration.py — old .env → settings.json.

Before Phase 5, the installer wrote env vars into a skill-local
``~/.claude/skills/gemini/.env`` file. Phase 5 moves them to
``~/.claude/settings.json``. This module is the one-time bridge: when
a user upgrades their skill install, any values in the legacy .env
get merged into the new settings.json and the old file is offered
for deletion.

Behavior:
- **Legacy file absent** → no-op. Nothing to migrate.
- **Legacy file present with values** → read, merge into the
  settings buffer for any KEY that isn't already there (never
  clobber existing settings.json values).
- **User confirms deletion** → rm the legacy file.
- **User declines** → keep the legacy file.
- **Non-interactive** (``yes=True`` or piped stdin) → auto-delete
  after merge so CI installs don't leave stale files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock

import pytest


def _write_legacy_env(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestNoLegacyFile:
    def test_absent_legacy_file_is_noop(self, tmp_path: Path) -> None:
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        buffer: dict[str, Any] = {"env": {"GEMINI_API_KEY": "existing"}}
        # Function must not raise; buffer unchanged.
        migrate_legacy_env_to_settings(legacy, buffer, yes=True, interactive=False)
        assert buffer == {"env": {"GEMINI_API_KEY": "existing"}}


class TestMergeIntoBuffer:
    def test_adds_legacy_keys_not_in_buffer(self, tmp_path: Path) -> None:
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(
            legacy,
            "GEMINI_API_KEY=AIzaSyFromLegacy1234567890123456789\n" "GEMINI_LIVE_TESTS=1\n",
        )
        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", return_value="y"):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "AIzaSyFromLegacy1234567890123456789"
        assert buffer["env"]["GEMINI_LIVE_TESTS"] == "1"

    def test_does_not_clobber_existing_values(self, tmp_path: Path) -> None:
        """Legacy file has a value for a key that the settings buffer
        already has. Buffer wins — we never destroy the newer value."""
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(legacy, "GEMINI_API_KEY=AIzaSyFromLegacy123456789012345678\n")
        buffer: dict[str, Any] = {"env": {"GEMINI_API_KEY": "newer-value"}}
        with mock.patch("builtins.input", return_value="y"):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "newer-value"

    def test_skips_blank_and_comment_lines(self, tmp_path: Path) -> None:
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(
            legacy,
            "# a comment\n" "\n" "GEMINI_LIVE_TESTS=1\n" "   \n" "# another comment\n",
        )
        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", return_value="y"):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert list(buffer["env"].keys()) == ["GEMINI_LIVE_TESTS"]

    def test_env_block_missing_is_created(self, tmp_path: Path) -> None:
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(legacy, "GEMINI_LIVE_TESTS=1\n")
        buffer: dict[str, Any] = {}
        with mock.patch("builtins.input", return_value="y"):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_LIVE_TESTS"] == "1"


class TestLegacyFileDeletion:
    def test_user_confirms_deletion(self, tmp_path: Path) -> None:
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(legacy, "GEMINI_LIVE_TESTS=1\n")
        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", return_value="y"):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert not legacy.exists()

    def test_user_declines_keeps_file(self, tmp_path: Path) -> None:
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(legacy, "GEMINI_LIVE_TESTS=1\n")
        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", return_value="n"):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert legacy.exists()

    def test_default_choice_is_no(self, tmp_path: Path) -> None:
        """Safe default: empty input (Enter) keeps the file. The user
        can always delete it manually later, but we should never
        destroy it without an explicit confirmation."""
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(legacy, "GEMINI_LIVE_TESTS=1\n")
        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", return_value=""):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert legacy.exists()

    def test_yes_flag_auto_deletes_after_merge(self, tmp_path: Path) -> None:
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(legacy, "GEMINI_LIVE_TESTS=1\n")
        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", side_effect=RuntimeError("no prompt")):
            migrate_legacy_env_to_settings(legacy, buffer, yes=True, interactive=False)

        assert not legacy.exists()
        assert buffer["env"]["GEMINI_LIVE_TESTS"] == "1"


class TestEmptyLegacyFile:
    def test_empty_legacy_file_still_offers_deletion(self, tmp_path: Path) -> None:
        """A legacy file with only blank / comment lines has nothing
        to migrate, but it's still stale — offer deletion anyway."""
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(legacy, "# nothing here\n\n")
        buffer: dict[str, Any] = {"env": {}}
        migrate_legacy_env_to_settings(legacy, buffer, yes=True, interactive=False)
        assert not legacy.exists()
        assert buffer == {"env": {}}


class TestInvalidLines:
    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        """A line without an ``=`` is not a valid env var and must be
        skipped rather than raising."""
        from core.cli.installer.legacy_migration import migrate_legacy_env_to_settings

        legacy = tmp_path / "legacy.env"
        _write_legacy_env(
            legacy,
            "GEMINI_LIVE_TESTS=1\n"
            "this is not an env line\n"
            "GEMINI_API_KEY=AIzaSyKey1234567890123456789012345678\n",
        )
        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", return_value="y"):
            migrate_legacy_env_to_settings(legacy, buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_LIVE_TESTS"] == "1"
        assert buffer["env"]["GEMINI_API_KEY"] == "AIzaSyKey1234567890123456789012345678"
