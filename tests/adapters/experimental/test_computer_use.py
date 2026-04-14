"""Tests for adapters/experimental/computer_use.py."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_action_response():
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "I'll click the button."},
                        {"computerUseAction": {"type": "click", "x": 100, "y": 200}},
                    ],
                    "role": "model",
                }
            }
        ],
    }


def _mock_text_only_response():
    return {
        "candidates": [
            {"content": {"parts": [{"text": "I can see the screen."}], "role": "model"}}
        ],
    }


class TestComputerUseGetParser:
    def test_has_prompt(self):
        from adapters.experimental.computer_use import get_parser

        args = get_parser().parse_args(["click the submit button"])
        assert args.prompt == "click the submit button"


class TestComputerUseRun:
    def test_sends_computer_use_tool(self, capsys):
        from adapters.experimental.computer_use import run

        with (
            patch(
                "adapters.experimental.computer_use.api_call", return_value=_mock_action_response()
            ) as mock,
            patch("adapters.experimental.computer_use.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="click button")
        body = mock.call_args.kwargs["body"]
        assert {"computerUse": {}} in body["tools"]

    def test_emits_actions_as_json(self, capsys):
        from adapters.experimental.computer_use import run

        with (
            patch(
                "adapters.experimental.computer_use.api_call", return_value=_mock_action_response()
            ),
            patch("adapters.experimental.computer_use.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="click button")
        data = json.loads(capsys.readouterr().out)
        assert data["type"] == "computer_actions"
        assert len(data["actions"]) == 1

    def test_text_only_response(self, capsys):
        from adapters.experimental.computer_use import run

        with (
            patch(
                "adapters.experimental.computer_use.api_call",
                return_value=_mock_text_only_response(),
            ),
            patch("adapters.experimental.computer_use.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="what do you see")
        assert "I can see" in capsys.readouterr().out
