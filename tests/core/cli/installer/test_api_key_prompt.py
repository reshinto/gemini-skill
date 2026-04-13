"""Tests for core/cli/installer/api_key_prompt.py — GEMINI_API_KEY setup.

The api_key_prompt module is the special-case interactive setup that
runs BEFORE the generic settings merge. It has exactly one
responsibility: populate the in-memory settings buffer's
``env.GEMINI_API_KEY`` entry with whatever the user wants before the
generic merge sees the key and would otherwise prompt as a conflict.

Three branches:

1. **Key already present, user chooses Keep** — no change.
2. **Key already present, user chooses Update** — prompt for new value
   (via ``getpass.getpass`` so input is not echoed), store it.
3. **Key absent** — prompt for value, store it (empty input OK).

Non-interactive / ``--yes`` modes skip the prompt entirely and leave
the buffer as-is; the generic merge downstream handles it.

All tests mock ``getpass.getpass`` and ``builtins.input`` to script
user choices.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest


class TestKeyAlreadyPresent:
    def test_keep_choice_leaves_value_unchanged(self, capsys: pytest.CaptureFixture[str]) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {"GEMINI_API_KEY": "AIzaSyExistingKey1234567890123456789"}}
        with mock.patch("builtins.input", return_value="k"):
            with mock.patch("getpass.getpass") as mock_getpass:
                prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "AIzaSyExistingKey1234567890123456789"
        mock_getpass.assert_not_called()
        # The existing value must NEVER appear in stdout.
        assert "AIzaSyExistingKey" not in capsys.readouterr().out

    def test_update_choice_prompts_and_replaces(self) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {
            "env": {"GEMINI_API_KEY": "AIzaSyOldKey1234567890123456789012345"}
        }
        with mock.patch("builtins.input", return_value="u"):
            with mock.patch(
                "getpass.getpass",
                return_value="AIzaSyNewKey1234567890123456789012345",
            ):
                prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "AIzaSyNewKey1234567890123456789012345"

    def test_default_choice_on_enter_is_keep(self) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {"GEMINI_API_KEY": "existing"}}
        with mock.patch("builtins.input", return_value=""):
            with mock.patch("getpass.getpass") as mock_getpass:
                prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "existing"
        mock_getpass.assert_not_called()

    def test_invalid_choice_reprompts(self) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {"GEMINI_API_KEY": "existing"}}
        # First invalid, then valid "k".
        with mock.patch("builtins.input", side_effect=["xyz", "k"]):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "existing"


class TestKeyAbsent:
    def test_absent_key_prompts_for_value_and_stores_it(self) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("getpass.getpass", return_value="AIzaSyNewKey1234567890123456789012345"):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "AIzaSyNewKey1234567890123456789012345"

    def test_absent_key_empty_input_stored_as_empty_string(self) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("getpass.getpass", return_value=""):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == ""

    def test_absent_key_strips_whitespace_from_input(self) -> None:
        """Copy-paste mistakes commonly introduce leading/trailing
        whitespace. Strip at the boundary."""
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        with mock.patch(
            "getpass.getpass", return_value="  AIzaSyKey1234567890123456789012345678  "
        ):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "AIzaSyKey1234567890123456789012345678"

    def test_env_block_missing_is_created(self) -> None:
        """A settings buffer without an ``env`` top-level key is a
        valid input — the prompt creates the block before writing."""
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {}
        with mock.patch("getpass.getpass", return_value="AIza-value"):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert "env" in buffer
        assert buffer["env"]["GEMINI_API_KEY"] == "AIza-value"


class TestNonInteractiveModes:
    def test_yes_flag_skips_prompt_entirely(self) -> None:
        """``--yes`` mode: the prompt is suppressed so a CI install
        never hangs waiting for stdin. The buffer is left unchanged;
        the generic merge downstream handles the default."""
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", side_effect=RuntimeError("should not prompt")):
            with mock.patch("getpass.getpass", side_effect=RuntimeError("should not prompt")):
                prompt_gemini_api_key(buffer, yes=True, interactive=False)

        # Untouched — merge_settings_env will add the default later.
        assert buffer == {"env": {}}

    def test_non_tty_stdin_skips_prompt_with_stderr_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("builtins.input", side_effect=RuntimeError("should not prompt")):
            with mock.patch("getpass.getpass", side_effect=RuntimeError("should not prompt")):
                prompt_gemini_api_key(buffer, yes=False, interactive=False)

        captured = capsys.readouterr()
        assert "non-interactive" in captured.err.lower()


class TestGetpassEchoFallbackGuard:
    def test_raises_when_getpass_warns_about_echo(self) -> None:
        """CR-8 from the canonical plan: ``getpass.getpass`` silently
        falls back to echoing input on unusual terminals. We detect
        the ``GetPassWarning`` and abort so a key is never entered
        into a scrollback-visible terminal without explicit user
        acknowledgement."""
        import getpass

        from core.cli.installer.api_key_prompt import prompt_gemini_api_key
        from core.cli.installer.venv import InstallError

        buffer: dict[str, Any] = {"env": {}}

        def fake_getpass(prompt: str = "") -> str:
            import warnings

            warnings.warn("Can not control echo", getpass.GetPassWarning)
            return "AIza-leaked"

        with mock.patch("getpass.getpass", side_effect=fake_getpass):
            with pytest.raises(InstallError, match="echo"):
                prompt_gemini_api_key(buffer, yes=False, interactive=True)

    def test_ignores_non_getpass_warnings(self) -> None:
        """A different warning class surfaced inside the getpass call
        must NOT be mistaken for an echo fallback. The guard only
        aborts on ``GetPassWarning``; anything else flows through."""
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}

        def fake_getpass(prompt: str = "") -> str:
            import warnings

            warnings.warn("some unrelated warning", UserWarning)
            return "AIzaSyRegularKey1234567890123456789012"

        with mock.patch("getpass.getpass", side_effect=fake_getpass):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "AIzaSyRegularKey1234567890123456789012"


class TestSecurityPrintContracts:
    def test_only_length_printed_never_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        """After the user enters a value, the confirmation line must
        report only the length (N chars) — never the value itself."""
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        secret = "AIzaSyTotallySecret1234567890123456789"
        with mock.patch("getpass.getpass", return_value=secret):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        captured = capsys.readouterr()
        assert secret not in captured.out
        assert secret not in captured.err
        assert str(len(secret)) in captured.out

    def test_unusual_prefix_warns_but_saves(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A value that doesn't start with ``AIzaSy`` is saved anyway
        (the heuristic might be wrong — Google could add new key
        formats) but a WARN line alerts the user."""
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("getpass.getpass", return_value="unusual-prefix-key"):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        assert buffer["env"]["GEMINI_API_KEY"] == "unusual-prefix-key"
        captured = capsys.readouterr()
        assert "WARN" in captured.out or "warn" in captured.out.lower()

    def test_empty_value_announces_leave_empty_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from core.cli.installer.api_key_prompt import prompt_gemini_api_key

        buffer: dict[str, Any] = {"env": {}}
        with mock.patch("getpass.getpass", return_value=""):
            prompt_gemini_api_key(buffer, yes=False, interactive=True)

        captured = capsys.readouterr()
        assert "empty" in captured.out.lower()
