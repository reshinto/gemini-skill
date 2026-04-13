"""Tests for adapters/tools/search.py — Google Search grounding."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


def _mock_search_response(text="Search result", with_grounding=False):
    resp = {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
            }
        ],
    }
    if with_grounding:
        resp["candidates"][0]["groundingMetadata"] = {
            "groundingChunks": [
                {"web": {"title": "Example", "uri": "https://example.com"}},
            ]
        }
    return resp


class TestSearchGetParser:
    def test_has_prompt(self):
        from adapters.tools.search import get_parser

        args = get_parser().parse_args(["what is the weather"])
        assert args.prompt == "what is the weather"


class TestSearchRun:
    def test_sends_google_search_tool(self, capsys):
        from adapters.tools.search import run

        with (
            patch("adapters.tools.search.api_call", return_value=_mock_search_response()) as mock,
            patch("adapters.tools.search.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="weather today")
        body = mock.call_args.kwargs["body"]
        assert {"googleSearch": {}} in body["tools"]

    def test_emits_text(self, capsys):
        from adapters.tools.search import run

        with (
            patch(
                "adapters.tools.search.api_call", return_value=_mock_search_response("Sunny today")
            ),
            patch("adapters.tools.search.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="weather")
        assert "Sunny today" in capsys.readouterr().out

    def test_includes_grounding_sources(self, capsys):
        from adapters.tools.search import run

        with (
            patch(
                "adapters.tools.search.api_call",
                return_value=_mock_search_response("result", with_grounding=True),
            ),
            patch("adapters.tools.search.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test")
        output = capsys.readouterr().out
        assert "Sources:" in output
        assert "Example" in output
        assert "https://example.com" in output

    def test_no_grounding_metadata(self, capsys):
        from adapters.tools.search import run

        with (
            patch("adapters.tools.search.api_call", return_value=_mock_search_response("plain")),
            patch("adapters.tools.search.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test")
        output = capsys.readouterr().out
        assert "Sources:" not in output


class TestSearchShowGrounding:
    """Phase 7: ``--show-grounding`` emits the grounding metadata as
    a JSON block alongside the text answer instead of the human-readable
    "Sources:" footer. Used by agents that need structured access to
    the grounding chunks (web queries, search entry point, chunk URIs)."""

    def test_parser_has_show_grounding_flag(self):
        import json as _json

        from adapters.tools.search import get_parser

        args = get_parser().parse_args(["q", "--show-grounding"])
        assert args.show_grounding is True

        args2 = get_parser().parse_args(["q"])
        assert args2.show_grounding is False
        del _json  # unused helper placeholder

    def test_show_grounding_emits_json_with_text_and_metadata(self, capsys):
        import json as _json

        from adapters.tools.search import run

        with (
            patch(
                "adapters.tools.search.api_call",
                return_value=_mock_search_response("Sunny today", with_grounding=True),
            ),
            patch("adapters.tools.search.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="weather", show_grounding=True)
        out = capsys.readouterr().out
        data = _json.loads(out)
        assert data["text"] == "Sunny today"
        assert data["grounding"]["groundingChunks"][0]["web"]["uri"] == "https://example.com"

    def test_show_grounding_with_no_grounding_returns_null_metadata(self, capsys):
        import json as _json

        from adapters.tools.search import run

        with (
            patch(
                "adapters.tools.search.api_call",
                return_value=_mock_search_response("plain"),
            ),
            patch("adapters.tools.search.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="q", show_grounding=True)
        data = _json.loads(capsys.readouterr().out)
        assert data["text"] == "plain"
        assert data["grounding"] is None

    def test_show_grounding_false_preserves_legacy_text_output(self, capsys):
        """Opt-out is the default — existing callers see the legacy
        human-readable output unchanged."""
        from adapters.tools.search import run

        with (
            patch(
                "adapters.tools.search.api_call",
                return_value=_mock_search_response("result", with_grounding=True),
            ),
            patch("adapters.tools.search.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="q", show_grounding=False)
        out = capsys.readouterr().out
        assert "Sources:" in out
        assert "Example" in out
