"""Tests for adapters/generation/text.py — text generation adapter."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


def _mock_response(text="Hello world"):
    return {
        "candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
            "cachedContentTokenCount": 0,
        },
    }


class TestTextGetParser:
    def test_has_prompt_arg(self):
        from adapters.generation.text import get_parser

        parser = get_parser()
        args = parser.parse_args(["hello"])
        assert args.prompt == "hello"

    def test_has_system_flag(self):
        from adapters.generation.text import get_parser

        parser = get_parser()
        args = parser.parse_args(["hello", "--system", "Be concise"])
        assert args.system == "Be concise"

    def test_has_temperature_flag(self):
        from adapters.generation.text import get_parser

        parser = get_parser()
        args = parser.parse_args(["hello", "--temperature", "0.5"])
        assert args.temperature == 0.5

    def test_has_max_tokens_flag(self):
        from adapters.generation.text import get_parser

        parser = get_parser()
        args = parser.parse_args(["hello", "--max-tokens", "1024"])
        assert args.max_tokens == 1024


class TestTextRun:
    def test_calls_api_with_prompt(self, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response()) as mock_api,
            patch("adapters.generation.text.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello")
        mock_api.assert_called_once()
        body = mock_api.call_args.kwargs["body"]
        assert body["contents"][0]["parts"][0]["text"] == "hello"

    def test_emits_response_text(self, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response("Test output")),
            patch("adapters.generation.text.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello")
        captured = capsys.readouterr()
        assert "Test output" in captured.out

    def test_uses_custom_model(self, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response()) as mock_api,
            patch("adapters.generation.text.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello", model="gemini-2.5-pro")
        endpoint = mock_api.call_args[0][0]
        assert "gemini-2.5-pro" in endpoint

    def test_includes_system_instruction(self, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response()) as mock_api,
            patch("adapters.generation.text.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello", system="Be brief")
        body = mock_api.call_args.kwargs["body"]
        assert "systemInstruction" in body

    def test_no_system_instruction_by_default(self, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response()) as mock_api,
            patch("adapters.generation.text.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello")
        body = mock_api.call_args.kwargs["body"]
        assert "systemInstruction" not in body

    def test_sets_generation_config(self, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response()) as mock_api,
            patch("adapters.generation.text.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello", max_tokens=1024, temperature=0.5)
        body = mock_api.call_args.kwargs["body"]
        assert body["generationConfig"]["maxOutputTokens"] == 1024
        assert body["generationConfig"]["temperature"] == 0.5

    def test_session_creates_new_session(self, tmp_path, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response()),
            patch("adapters.generation.text.load_config") as mock_cfg,
            patch("adapters.generation.text.Path") as mock_path,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            mock_path.home.return_value = tmp_path
            mock_path.return_value = tmp_path
            mock_path.side_effect = lambda x: type(tmp_path)(x) if isinstance(x, str) else x
            # Just verify it doesn't crash with session flag
            run(prompt="hello", session="test-session")

    def test_session_continues_existing(self, tmp_path, capsys):
        from adapters.generation.text import run
        from core.state.session_state import SessionState

        # Create an existing session with history
        sessions_dir = tmp_path / "sessions"
        sessions = SessionState(sessions_dir=sessions_dir)
        sessions.create("existing")
        sessions.append_message("existing", {"role": "user", "parts": [{"text": "prior msg"}]})
        sessions.append_message(
            "existing", {"role": "model", "parts": [{"text": "prior response"}]}
        )

        with (
            patch(
                "adapters.generation.text.api_call", return_value=_mock_response("Continued")
            ) as mock_api,
            patch("adapters.generation.text.load_config") as mock_cfg,
            patch("core.state.session_state.SessionState", return_value=sessions),
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="follow up", session="existing")

        body = mock_api.call_args.kwargs["body"]
        # Contents: 2 prior messages + new prompt = 3
        assert len(body["contents"]) >= 3

    def test_continue_session_flag(self, capsys):
        from adapters.generation.text import run

        with (
            patch("adapters.generation.text.api_call", return_value=_mock_response()),
            patch("adapters.generation.text.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            # continue_session with no existing session — should not crash
            run(prompt="hello", continue_session=True)
