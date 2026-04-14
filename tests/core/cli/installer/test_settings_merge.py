"""Tests for core/cli/installer/settings_merge.py — ~/.claude/settings.json merge.

The settings_merge module is the part of Phase 5 that teaches the
installer to write the skill's env vars into the user-global
``~/.claude/settings.json`` instead of a skill-local .env file. The
installer calls this module ONCE at the end of the install flow with
the default env keys the skill needs, and it takes care of the rest:

- File doesn't exist → create it with the defaults.
- File exists but is malformed JSON → abort (don't overwrite).
- File exists and has a clean env block → silently add missing keys.
- File exists and a default key ALREADY has a value → prompt the user
  per-key (replace / skip / quit), NEVER echoing the existing value
  because it might be a secret.
- Backup the original ~/.claude/settings.json once at first touch so
  users have a recovery path.

All non-conflicting keys merge silently; every conflict is a separate
interactive prompt so the user stays in control of each decision.
The default behavior on ``Enter`` is ``skip`` — never destroy data.

Tests mock ``builtins.input`` to script user choices so the suite is
fully deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest


# Canonical default keys the installer writes — matches the plan's
# _DEFAULT_ENV_KEYS in the same order. The fixture is used by every
# test so any reorder is a single-point update.
_DEFAULTS: dict[str, str] = {
    "GEMINI_API_KEY": "",
    "GEMINI_IS_SDK_PRIORITY": "true",
    "GEMINI_IS_RAWHTTP_PRIORITY": "false",
    "GEMINI_LIVE_TESTS": "0",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


class TestCreateWhenMissing:
    def test_creates_file_with_defaults_when_settings_absent(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        result = merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

        assert settings_path.exists()
        data = _read(settings_path)
        assert data == {"env": dict(_DEFAULTS)}
        # The per-key result summary should list every key as "added".
        assert result == {k: "added" for k in _DEFAULTS}

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "deep" / "nested" / "settings.json"
        merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)
        assert settings_path.exists()


class TestMalformedAborts:
    def test_malformed_json_raises_install_error(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env
        from core.cli.installer.venv import InstallError

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("not json {")
        with pytest.raises(InstallError, match="not valid JSON"):
            merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

    def test_malformed_file_is_not_overwritten(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env
        from core.cli.installer.venv import InstallError

        settings_path = tmp_path / "settings.json"
        original = "not json {"
        settings_path.write_text(original)
        with pytest.raises(InstallError):
            merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)
        assert settings_path.read_text() == original


class TestAddEnvBlockWhenMissing:
    def test_preserves_other_top_level_keys(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        original = {
            "model": "claude-opus-4-6",
            "permissions": {"allow": ["Bash(git status)"]},
            "hooks": {"PreToolUse": []},
        }
        settings_path.write_text(json.dumps(original))
        merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

        data = _read(settings_path)
        # The env block must be added; every other top-level key stays.
        assert data["env"] == dict(_DEFAULTS)
        assert data["model"] == "claude-opus-4-6"
        assert data["permissions"] == {"allow": ["Bash(git status)"]}
        assert data["hooks"] == {"PreToolUse": []}


class TestSilentMergeOfNonConflictingKeys:
    def test_adds_only_missing_keys(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"OTHER_TOOL_KEY": "xyz"}}))

        result = merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

        data = _read(settings_path)
        assert data["env"]["OTHER_TOOL_KEY"] == "xyz"
        for k, v in _DEFAULTS.items():
            assert data["env"][k] == v
        # Every default key reports "added"; no conflict prompts.
        assert all(state == "added" for state in result.values())


class TestPreResolvedOverride:
    """The ``pre_resolved`` kwarg lets the orchestrator inject values
    from legacy migration / API-key prompt in a single atomic merge."""

    def test_pre_resolved_value_added_when_key_absent(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        result = merge_settings_env(
            settings_path,
            _DEFAULTS,
            yes=True,
            interactive=False,
            pre_resolved={"GEMINI_API_KEY": "AIzaSyFromBuffer123456789012345678901"},
        )

        data = _read(settings_path)
        assert data["env"]["GEMINI_API_KEY"] == "AIzaSyFromBuffer123456789012345678901"
        assert result["GEMINI_API_KEY"] == "added"

    def test_pre_resolved_value_replaces_existing_file_value(self, tmp_path: Path) -> None:
        """If the on-disk env had a different value and the buffer
        overrides it, the result state is 'replaced' so the
        orchestrator can surface what happened. Covers the branch
        in merge_settings_env that checks ``original_env[key] !=
        env[key]`` for the pre-resolved-key path."""
        import json

        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_LIVE_TESTS": "0"}}))
        result = merge_settings_env(
            settings_path,
            _DEFAULTS,
            yes=True,
            interactive=False,
            pre_resolved={"GEMINI_LIVE_TESTS": "1"},
        )

        assert _read(settings_path)["env"]["GEMINI_LIVE_TESTS"] == "1"
        assert result["GEMINI_LIVE_TESTS"] == "replaced"

    def test_empty_pre_resolved_value_is_ignored(self, tmp_path: Path) -> None:
        """Empty overrides must not clobber defaults or existing
        values — they would just write nothing useful."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        merge_settings_env(
            settings_path,
            _DEFAULTS,
            yes=True,
            interactive=False,
            pre_resolved={"GEMINI_IS_SDK_PRIORITY": ""},
        )

        # Empty override ignored → default ("true") wrote.
        assert _read(settings_path)["env"]["GEMINI_IS_SDK_PRIORITY"] == "true"

    def test_secret_key_default_is_redacted_in_prompt(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Even if a future caller-side mistake injects a real key
        as a "default", the conflict prompt must not echo it."""
        from core.cli.installer.settings_merge import merge_settings_env

        import json

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": "existing"}}))
        # Inject a fake key as the default — the prompt must redact it.
        leaked_default = "AIzaSyDefault123456789012345678901234567"
        with mock.patch("builtins.input", return_value="s"):
            merge_settings_env(
                settings_path,
                {"GEMINI_API_KEY": leaked_default},
                yes=False,
                interactive=True,
            )

        captured = capsys.readouterr()
        assert leaked_default not in captured.out
        # Both "existing" and "default" appear as REDACTED in the prompt.
        assert captured.out.count("REDACTED") >= 2


class TestDuplicateKeyConflict:
    def test_prompt_shown_for_duplicate_key(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": "AIzaSyOld12345"}}))
        # User chooses "skip" (keep existing).
        with mock.patch("builtins.input", return_value="s"):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)

        data = _read(settings_path)
        assert data["env"]["GEMINI_API_KEY"] == "AIzaSyOld12345"
        assert result["GEMINI_API_KEY"] == "kept"

    def test_replace_choice_overwrites_value(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_IS_SDK_PRIORITY": "false"}}))
        with mock.patch("builtins.input", return_value="r"):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)

        data = _read(settings_path)
        assert data["env"]["GEMINI_IS_SDK_PRIORITY"] == "true"  # default
        assert result["GEMINI_IS_SDK_PRIORITY"] == "replaced"

    def test_quit_aborts_with_install_error(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env
        from core.cli.installer.venv import InstallError

        settings_path = tmp_path / "settings.json"
        original = {"env": {"GEMINI_API_KEY": "existing"}}
        settings_path.write_text(json.dumps(original))
        with mock.patch("builtins.input", return_value="q"):
            with pytest.raises(InstallError, match="aborted"):
                merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)

        # File must be unchanged after quit.
        assert _read(settings_path) == original

    def test_default_choice_is_skip_on_enter(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": "existing"}}))
        # Empty string simulates pressing Enter.
        with mock.patch("builtins.input", return_value=""):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)

        assert _read(settings_path)["env"]["GEMINI_API_KEY"] == "existing"
        assert result["GEMINI_API_KEY"] == "kept"

    def test_invalid_input_reprompts(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": "existing"}}))
        # First invalid input, then a valid "s".
        with mock.patch("builtins.input", side_effect=["xyz", "s"]):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)
        assert result["GEMINI_API_KEY"] == "kept"

    def test_multiple_conflicts_prompted_independently(self, tmp_path: Path) -> None:
        """Two duplicate keys → two separate prompts, decisions tracked
        per key."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "env": {
                        "GEMINI_API_KEY": "existing-key",
                        "GEMINI_LIVE_TESTS": "1",
                    }
                }
            )
        )
        # First conflict replace, second skip.
        with mock.patch("builtins.input", side_effect=["r", "s"]):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)

        data = _read(settings_path)
        assert data["env"]["GEMINI_API_KEY"] == ""  # replaced with default
        assert data["env"]["GEMINI_LIVE_TESTS"] == "1"  # kept
        assert result["GEMINI_API_KEY"] == "replaced"
        assert result["GEMINI_LIVE_TESTS"] == "kept"


class TestSecretRedaction:
    def test_never_prints_existing_value_in_prompt(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The conflict prompt must NOT show the existing value — it
        could be a secret. The literal token ``<REDACTED — see
        settings.json>`` appears instead."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        leaked_key = "AIzaSyVerySecretKey1234567890123456789"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": leaked_key}}))
        with mock.patch("builtins.input", return_value="s"):
            merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)

        captured = capsys.readouterr()
        # The secret must NEVER appear in stdout or stderr.
        assert leaked_key not in captured.out
        assert leaked_key not in captured.err
        # The redaction marker must appear instead.
        assert "REDACTED" in captured.out


class TestYesFlagAutoSkips:
    def test_yes_flag_auto_skips_every_conflict(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "env": {
                        "GEMINI_API_KEY": "existing",
                        "GEMINI_LIVE_TESTS": "1",
                    }
                }
            )
        )
        # yes=True → no input() calls. If input is called, the test
        # will hang, so we patch it to catch that regression.
        with mock.patch("builtins.input", side_effect=RuntimeError("should not prompt")):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

        data = _read(settings_path)
        assert data["env"]["GEMINI_API_KEY"] == "existing"
        assert data["env"]["GEMINI_LIVE_TESTS"] == "1"
        assert result["GEMINI_API_KEY"] == "kept"
        assert result["GEMINI_LIVE_TESTS"] == "kept"

    def test_non_interactive_stdin_auto_skips(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": "existing"}}))
        with mock.patch("builtins.input", side_effect=RuntimeError("should not prompt")):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=False)

        assert result["GEMINI_API_KEY"] == "kept"
        # Warning about non-interactive skip should land on stderr.
        assert "non-interactive" in capsys.readouterr().err.lower()


class TestEmptyStringBothSides:
    def test_empty_string_on_both_sides_silent_no_prompt(self, tmp_path: Path) -> None:
        """CR-14 from the canonical plan: if existing value is "" AND
        the installer default is "", suppress the prompt entirely —
        nobody intentionally stores "" and forcing a user decision
        is pure noise."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": ""}}))
        # input should NEVER be called — if it is, the test fails.
        with mock.patch("builtins.input", side_effect=RuntimeError("no prompt expected")):
            result = merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=True)

        assert _read(settings_path)["env"]["GEMINI_API_KEY"] == ""
        # Empty-vs-empty is reported as "kept" (no change, no conflict).
        assert result["GEMINI_API_KEY"] == "kept"


class TestBackupOnFirstTouch:
    def test_first_install_creates_backup(self, tmp_path: Path) -> None:
        """Per CR-13: back up ~/.claude/settings.json once at first touch
        so users have a recovery path."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        original_content = {"env": {"OTHER": "x"}, "model": "claude"}
        settings_path.write_text(json.dumps(original_content))
        merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

        backup = settings_path.with_name("settings.json.pre-gemini-skill.bak")
        assert backup.exists()
        # The backup holds the ORIGINAL content, pre-merge.
        assert json.loads(backup.read_text()) == original_content

    def test_subsequent_install_does_not_overwrite_backup(self, tmp_path: Path) -> None:
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"OTHER": "x"}}))
        merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

        backup = settings_path.with_name("settings.json.pre-gemini-skill.bak")
        backup_mtime_first = backup.stat().st_mtime_ns
        backup_content_first = backup.read_text()

        # Second install — backup must not be touched.
        merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)
        assert backup.stat().st_mtime_ns == backup_mtime_first
        assert backup.read_text() == backup_content_first

    def test_no_backup_created_when_file_did_not_exist(self, tmp_path: Path) -> None:
        """If there was no pre-existing settings.json, there is nothing
        to back up — the backup file should NOT be created as an
        empty artifact."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

        backup = settings_path.with_name("settings.json.pre-gemini-skill.bak")
        assert not backup.exists()


class TestNonDictEnvBlock:
    def test_env_is_not_a_dict_raises(self, tmp_path: Path) -> None:
        """Defensive: if a user's settings.json has ``env`` set to a
        non-dict (e.g. a list), we can't safely merge — abort."""
        from core.cli.installer.settings_merge import merge_settings_env
        from core.cli.installer.venv import InstallError

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": ["not", "a", "dict"]}))
        with pytest.raises(InstallError, match="env"):
            merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)

    def test_top_level_is_not_a_dict_raises(self, tmp_path: Path) -> None:
        """Top-level JSON value that isn't an object (e.g. a list or
        scalar) is just as invalid as malformed JSON — the installer
        can't merge into something that isn't an object."""
        from core.cli.installer.settings_merge import merge_settings_env
        from core.cli.installer.venv import InstallError

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(["not", "a", "dict"]))
        with pytest.raises(InstallError, match="JSON object"):
            merge_settings_env(settings_path, _DEFAULTS, yes=True, interactive=False)


class TestNonInteractiveWarningOnce:
    def test_warning_fires_only_once_per_merge_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Two conflicts in the same non-interactive run → one
        warning line, not two. The warning is rate-limited via a
        module-level flag; this test pins the rate limit."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "env": {
                        "GEMINI_API_KEY": "existing",
                        "GEMINI_LIVE_TESTS": "1",
                    }
                }
            )
        )
        merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=False)
        captured = capsys.readouterr()
        # The substring appears at most once even with two conflicts.
        assert captured.err.count("non-interactive install") == 1

    def test_warning_resets_between_calls(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Two back-to-back ``merge_settings_env`` invocations must each
        emit their own warning. The rate-limit is per-call (via a
        local flag) not per-process — this pins the behavior after the
        removal of the module-level global."""
        from core.cli.installer.settings_merge import merge_settings_env

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"env": {"GEMINI_API_KEY": "existing"}}))
        merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=False)
        merge_settings_env(settings_path, _DEFAULTS, yes=False, interactive=False)
        captured = capsys.readouterr()
        # Two separate calls → two warning lines (one per call).
        assert captured.err.count("non-interactive install") == 2
