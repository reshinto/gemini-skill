"""Tests for adapters/generation/streaming.py."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class TestStreamingGetParser:
    def test_has_prompt_arg(self):
        from adapters.generation.streaming import get_parser

        args = get_parser().parse_args(["hello"])
        assert args.prompt == "hello"


class TestStreamingRun:
    def test_calls_stream_generate_content(self, capsys):
        from adapters.generation.streaming import run

        chunks = iter(
            [
                {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]},
                {"candidates": [{"content": {"parts": [{"text": " world"}]}}]},
            ]
        )

        with (
            patch(
                "adapters.generation.streaming.stream_generate_content", return_value=chunks
            ) as mock_stream,
            patch("adapters.generation.streaming.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(prompt="hello")

        mock_stream.assert_called_once()
        captured = capsys.readouterr().out
        assert "Hello" in captured
        assert "world" in captured

    def test_handles_empty_chunks(self, capsys):
        from adapters.generation.streaming import run

        chunks = iter(
            [
                {"candidates": []},
                {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
            ]
        )

        with (
            patch("adapters.generation.streaming.stream_generate_content", return_value=chunks),
            patch("adapters.generation.streaming.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(prompt="hello")

        assert "ok" in capsys.readouterr().out

    def test_handles_non_text_parts(self, capsys):
        from adapters.generation.streaming import run

        chunks = iter(
            [
                {"candidates": [{"content": {"parts": [{"inlineData": {}}]}}]},
            ]
        )

        with (
            patch("adapters.generation.streaming.stream_generate_content", return_value=chunks),
            patch("adapters.generation.streaming.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(prompt="hello")
        # Should not crash

    def test_uses_custom_model(self, capsys):
        from adapters.generation.streaming import run

        with (
            patch(
                "adapters.generation.streaming.stream_generate_content", return_value=iter([])
            ) as mock_stream,
            patch("adapters.generation.streaming.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(prompt="hello", model="gemini-2.5-pro")

        assert mock_stream.call_args[0][0] == "gemini-2.5-pro"
