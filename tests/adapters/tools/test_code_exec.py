"""Tests for adapters/tools/code_exec.py."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


def _mock_code_response():
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Let me calculate that."},
                        {
                            "executableCode": {"code": "print(2+2)", "language": "PYTHON"},
                            "id": "exec-1",
                        },
                        {
                            "codeExecutionResult": {"output": "4", "outcome": "OUTCOME_OK"},
                            "id": "result-1",
                        },
                        {"text": "The answer is 4."},
                    ],
                    "role": "model",
                }
            }
        ],
    }


def _mock_text_only_response():
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "No code needed."}],
                    "role": "model",
                }
            }
        ],
    }


class TestCodeExecGetParser:
    def test_has_prompt_arg(self):
        from adapters.tools.code_exec import get_parser

        args = get_parser().parse_args(["calculate 2+2"])
        assert args.prompt == "calculate 2+2"


class TestCodeExecRun:
    def test_sends_code_execution_tool(self, capsys):
        from adapters.tools.code_exec import run

        with (
            patch(
                "adapters.tools.code_exec.api_call", return_value=_mock_code_response()
            ) as mock_api,
            patch("adapters.tools.code_exec.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="calculate 2+2")

        body = mock_api.call_args.kwargs["body"]
        assert {"codeExecution": {}} in body["tools"]

    def test_includes_code_in_output(self, capsys):
        from adapters.tools.code_exec import run

        with (
            patch("adapters.tools.code_exec.api_call", return_value=_mock_code_response()),
            patch("adapters.tools.code_exec.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="calculate 2+2")

        output = capsys.readouterr().out
        assert "print(2+2)" in output
        assert "OUTCOME_OK" in output
        assert "The answer is 4" in output

    def test_text_only_response(self, capsys):
        from adapters.tools.code_exec import run

        with (
            patch("adapters.tools.code_exec.api_call", return_value=_mock_text_only_response()),
            patch("adapters.tools.code_exec.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello")

        assert "No code needed" in capsys.readouterr().out

    def test_uses_custom_model(self, capsys):
        from adapters.tools.code_exec import run

        with (
            patch(
                "adapters.tools.code_exec.api_call", return_value=_mock_text_only_response()
            ) as mock_api,
            patch("adapters.tools.code_exec.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello", model="gemini-2.5-pro")

        endpoint = mock_api.call_args[0][0]
        assert "gemini-2.5-pro" in endpoint
