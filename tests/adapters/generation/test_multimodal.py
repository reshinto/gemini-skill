"""Tests for adapters/generation/multimodal.py."""

from __future__ import annotations

import base64
from unittest.mock import patch, MagicMock

import pytest


def _mock_response(text="Multimodal response"):
    return {
        "candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
            "cachedContentTokenCount": 0,
        },
    }


class TestMultimodalGetParser:
    def test_has_prompt_arg(self):
        from adapters.generation.multimodal import get_parser

        args = get_parser().parse_args(["describe this"])
        assert args.prompt == "describe this"

    def test_has_file_flag(self):
        from adapters.generation.multimodal import get_parser

        args = get_parser().parse_args(["describe", "--file", "img.png"])
        assert args.file == ["img.png"]

    def test_multiple_files(self):
        from adapters.generation.multimodal import get_parser

        args = get_parser().parse_args(["describe", "--file", "a.png", "--file", "b.pdf"])
        assert len(args.file) == 2

    def test_has_mime_flag(self):
        from adapters.generation.multimodal import get_parser

        args = get_parser().parse_args(["describe", "--mime", "image/png"])
        assert args.mime == "image/png"


class TestMultimodalRun:
    def test_sends_file_as_inline_data(self, tmp_path, capsys):
        from adapters.generation.multimodal import run

        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n")

        with (
            patch(
                "adapters.generation.multimodal.api_call", return_value=_mock_response()
            ) as mock_api,
            patch("adapters.generation.multimodal.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="describe", file=[str(f)])

        body = mock_api.call_args.kwargs["body"]
        parts = body["contents"][0]["parts"]
        assert any("inlineData" in p for p in parts)
        assert parts[-1]["text"] == "describe"

    def test_no_files_sends_text_only(self, capsys):
        from adapters.generation.multimodal import run

        with (
            patch(
                "adapters.generation.multimodal.api_call", return_value=_mock_response()
            ) as mock_api,
            patch("adapters.generation.multimodal.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="hello")

        body = mock_api.call_args.kwargs["body"]
        assert len(body["contents"][0]["parts"]) == 1

    def test_mime_override(self, tmp_path, capsys):
        from adapters.generation.multimodal import run

        f = tmp_path / "data.bin"
        f.write_bytes(b"binary")

        with (
            patch(
                "adapters.generation.multimodal.api_call", return_value=_mock_response()
            ) as mock_api,
            patch("adapters.generation.multimodal.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="describe", file=[str(f)], mime="application/custom")

        body = mock_api.call_args.kwargs["body"]
        inline = body["contents"][0]["parts"][0]["inlineData"]
        assert inline["mimeType"] == "application/custom"

    def test_emits_response(self, capsys):
        from adapters.generation.multimodal import run

        with (
            patch(
                "adapters.generation.multimodal.api_call",
                return_value=_mock_response("Image shows a cat"),
            ),
            patch("adapters.generation.multimodal.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="describe")
        assert "Image shows a cat" in capsys.readouterr().out
