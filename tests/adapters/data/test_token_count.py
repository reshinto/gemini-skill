"""Tests for adapters/data/token_count.py."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


class TestTokenCountGetParser:
    def test_has_text_arg(self):
        from adapters.data.token_count import get_parser

        args = get_parser().parse_args(["hello world"])
        assert args.text == "hello world"


class TestTokenCountRun:
    def test_calls_count_tokens_endpoint(self, capsys):
        from adapters.data.token_count import run

        with (
            patch(
                "adapters.data.token_count.api_call", return_value={"totalTokens": 42}
            ) as mock_api,
            patch("adapters.data.token_count.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello world")

        endpoint = mock_api.call_args[0][0]
        assert "countTokens" in endpoint

    def test_returns_token_count(self, capsys):
        from adapters.data.token_count import run

        with (
            patch("adapters.data.token_count.api_call", return_value={"totalTokens": 42}),
            patch("adapters.data.token_count.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello world")

        data = json.loads(capsys.readouterr().out)
        assert data["totalTokens"] == 42

    def test_uses_custom_model(self, capsys):
        from adapters.data.token_count import run

        with (
            patch(
                "adapters.data.token_count.api_call", return_value={"totalTokens": 10}
            ) as mock_api,
            patch("adapters.data.token_count.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello", model="gemini-2.5-pro")

        endpoint = mock_api.call_args[0][0]
        assert "gemini-2.5-pro" in endpoint

    def test_handles_missing_total(self, capsys):
        from adapters.data.token_count import run

        with (
            patch("adapters.data.token_count.api_call", return_value={}),
            patch("adapters.data.token_count.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello")

        data = json.loads(capsys.readouterr().out)
        assert data["totalTokens"] == 0
