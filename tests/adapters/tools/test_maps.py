"""Tests for adapters/tools/maps.py — Google Maps grounding.

Must assert: sources follow content, title displayed, uri linked,
attribution line, googleMapsUri fallback.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


def _mock_maps_response(text="Near Tokyo Station", chunks=None):
    resp = {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
            }
        ],
    }
    if chunks is not None:
        resp["candidates"][0]["groundingMetadata"] = {"groundingChunks": chunks}
    return resp


class TestMapsGetParser:
    def test_has_prompt(self):
        from adapters.tools.maps import get_parser

        args = get_parser().parse_args(["restaurants near me"])
        assert args.prompt == "restaurants near me"


class TestMapsRun:
    def test_sends_google_maps_tool(self, capsys):
        from adapters.tools.maps import run

        with (
            patch("adapters.tools.maps.api_call", return_value=_mock_maps_response()) as mock,
            patch("adapters.tools.maps.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="restaurants")
        body = mock.call_args.kwargs["body"]
        assert {"googleMaps": {}} in body["tools"]

    def test_emits_answer_then_sources(self, capsys):
        from adapters.tools.maps import run

        chunks = [
            {"maps": {"title": "Sushi Place", "uri": "https://maps.google.com/place/1"}},
        ]
        with (
            patch(
                "adapters.tools.maps.api_call",
                return_value=_mock_maps_response("Great sushi", chunks),
            ),
            patch("adapters.tools.maps.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="sushi")
        output = capsys.readouterr().out
        # Answer before sources
        answer_pos = output.index("Great sushi")
        sources_pos = output.index("Sources:")
        assert answer_pos < sources_pos
        # Source with title and uri
        assert "[Sushi Place]" in output
        assert "https://maps.google.com/place/1" in output
        assert "-- Google Maps" in output

    def test_attribution_line_present(self, capsys):
        from adapters.tools.maps import run

        with (
            patch("adapters.tools.maps.api_call", return_value=_mock_maps_response()),
            patch("adapters.tools.maps.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test")
        assert "This answer uses Google Maps data." in capsys.readouterr().out

    def test_prefers_uri_over_google_maps_uri(self, capsys):
        from adapters.tools.maps import run

        chunks = [
            {
                "maps": {
                    "title": "Place",
                    "uri": "https://primary.url",
                    "googleMapsUri": "https://fallback.url",
                }
            },
        ]
        with (
            patch("adapters.tools.maps.api_call", return_value=_mock_maps_response("text", chunks)),
            patch("adapters.tools.maps.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test")
        output = capsys.readouterr().out
        assert "https://primary.url" in output
        assert "https://fallback.url" not in output

    def test_falls_back_to_google_maps_uri(self, capsys):
        from adapters.tools.maps import run

        chunks = [
            {"maps": {"title": "Place", "googleMapsUri": "https://fallback.url"}},
        ]
        with (
            patch("adapters.tools.maps.api_call", return_value=_mock_maps_response("text", chunks)),
            patch("adapters.tools.maps.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test")
        assert "https://fallback.url" in capsys.readouterr().out

    def test_no_grounding_still_has_attribution(self, capsys):
        from adapters.tools.maps import run

        with (
            patch("adapters.tools.maps.api_call", return_value=_mock_maps_response()),
            patch("adapters.tools.maps.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="test")
        output = capsys.readouterr().out
        assert "Sources:" not in output
        assert "Google Maps data" in output
