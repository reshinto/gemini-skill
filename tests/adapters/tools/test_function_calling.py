"""Tests for adapters/tools/function_calling.py."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_fc_response():
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {"name": "get_weather", "args": {"city": "Tokyo"}},
                            "id": "call-1",
                            "tool_type": "function_calling",
                        }
                    ],
                    "role": "model",
                }
            }
        ],
    }


def _mock_text_response():
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "I don't need to call any functions."}],
                    "role": "model",
                }
            }
        ],
    }


class TestFunctionCallingGetParser:
    def test_has_prompt_and_tools(self):
        from adapters.tools.function_calling import get_parser

        args = get_parser().parse_args(["weather?", "--tools", '{"functionDeclarations": []}'])
        assert args.prompt == "weather?"
        assert args.tools == '{"functionDeclarations": []}'


class TestFunctionCallingRun:
    def test_sends_tools_in_request(self, capsys):
        from adapters.tools.function_calling import run

        tools = '[{"functionDeclarations": [{"name": "f"}]}]'

        with (
            patch(
                "adapters.tools.function_calling.api_call", return_value=_mock_fc_response()
            ) as mock_api,
            patch("adapters.tools.function_calling.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="weather?", tools=tools)

        body = mock_api.call_args.kwargs["body"]
        assert "tools" in body

    def test_emits_function_calls_as_json(self, capsys):
        from adapters.tools.function_calling import run

        with (
            patch("adapters.tools.function_calling.api_call", return_value=_mock_fc_response()),
            patch("adapters.tools.function_calling.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="weather?", tools='[{"functionDeclarations": []}]')

        data = json.loads(capsys.readouterr().out)
        assert data["type"] == "function_calls"
        assert len(data["calls"]) == 1
        assert data["calls"][0]["functionCall"]["name"] == "get_weather"

    def test_emits_text_when_no_function_calls(self, capsys):
        from adapters.tools.function_calling import run

        with (
            patch("adapters.tools.function_calling.api_call", return_value=_mock_text_response()),
            patch("adapters.tools.function_calling.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello", tools='[{"functionDeclarations": []}]')

        assert "don't need" in capsys.readouterr().out

    def test_loads_tools_from_file(self, tmp_path, capsys):
        from adapters.tools.function_calling import run

        tools_file = tmp_path / "tools.json"
        tools_file.write_text('[{"functionDeclarations": [{"name": "f"}]}]')

        with (
            patch(
                "adapters.tools.function_calling.api_call", return_value=_mock_fc_response()
            ) as mock_api,
            patch("adapters.tools.function_calling.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test", tools=str(tools_file))

        body = mock_api.call_args.kwargs["body"]
        assert body["tools"][0]["functionDeclarations"][0]["name"] == "f"

    def test_wraps_single_tool_object(self, capsys):
        from adapters.tools.function_calling import run

        tools = '{"functionDeclarations": [{"name": "f"}]}'

        with (
            patch(
                "adapters.tools.function_calling.api_call", return_value=_mock_fc_response()
            ) as mock_api,
            patch("adapters.tools.function_calling.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test", tools=tools)

        body = mock_api.call_args.kwargs["body"]
        assert isinstance(body["tools"], list)
