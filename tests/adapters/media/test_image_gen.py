"""Tests for adapters/media/image_gen.py — image generation adapter."""
from __future__ import annotations

import base64
import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_image_response(data=b"\x89PNG", mime="image/png"):
    b64 = base64.b64encode(data).decode()
    return {
        "candidates": [{
            "content": {
                "parts": [{"inlineData": {"mimeType": mime, "data": b64}}],
                "role": "model",
            }
        }],
    }


def _mock_text_only_response():
    return {
        "candidates": [{
            "content": {"parts": [{"text": "Cannot generate image."}], "role": "model"}
        }],
    }


class TestImageGenGetParser:
    def test_has_prompt(self):
        from adapters.media.image_gen import get_parser
        args = get_parser().parse_args(["a cute cat"])
        assert args.prompt == "a cute cat"

    def test_has_output_dir(self):
        from adapters.media.image_gen import get_parser
        args = get_parser().parse_args(["cat", "--output-dir", "/tmp"])
        assert args.output_dir == "/tmp"


class TestImageGenRun:
    def test_dry_run_skips(self, capsys):
        from adapters.media.image_gen import run
        run(prompt="cat", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_saves_image_to_file(self, tmp_path, capsys):
        from adapters.media.image_gen import run
        with patch("adapters.media.image_gen.api_call", return_value=_mock_image_response()), \
             patch("adapters.media.image_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True)
        data = json.loads(capsys.readouterr().out)
        assert data["mime_type"] == "image/png"
        assert data["size_bytes"] > 0
        assert tmp_path.name in data["path"] or "gemini-skill-" in data["path"]

    def test_never_outputs_base64(self, capsys):
        from adapters.media.image_gen import run
        img_data = b"\x89PNG" * 1000
        with patch("adapters.media.image_gen.api_call", return_value=_mock_image_response(img_data)), \
             patch("adapters.media.image_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="cat", execute=True)
        output = capsys.readouterr().out
        assert base64.b64encode(img_data).decode() not in output

    def test_emits_text_when_no_image(self, capsys):
        from adapters.media.image_gen import run
        with patch("adapters.media.image_gen.api_call", return_value=_mock_text_only_response()), \
             patch("adapters.media.image_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="cat", execute=True)
        assert "Cannot generate" in capsys.readouterr().out

    def test_uses_custom_output_dir(self, tmp_path, capsys):
        from adapters.media.image_gen import run
        with patch("adapters.media.image_gen.api_call", return_value=_mock_image_response()), \
             patch("adapters.media.image_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="cat", execute=True, output_dir=str(tmp_path))
        data = json.loads(capsys.readouterr().out)
        assert str(tmp_path) in data["path"]

    def test_sets_response_modalities(self, capsys):
        from adapters.media.image_gen import run
        with patch("adapters.media.image_gen.api_call", return_value=_mock_image_response()) as mock, \
             patch("adapters.media.image_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="cat", execute=True)
        body = mock.call_args.kwargs["body"]
        assert body["generationConfig"]["responseModalities"] == ["IMAGE", "TEXT"]


class TestImageMimeMap:
    def test_image_mime_map_known(self):
        from adapters.media.image_gen import _IMAGE_MIME_MAP
        from core.adapter.helpers import mime_to_ext
        assert mime_to_ext("image/png", _IMAGE_MIME_MAP, ".png") == ".png"
        assert mime_to_ext("image/jpeg", _IMAGE_MIME_MAP, ".png") == ".jpg"
        assert mime_to_ext("image/webp", _IMAGE_MIME_MAP, ".png") == ".webp"

    def test_image_mime_map_fallback(self):
        from adapters.media.image_gen import _IMAGE_MIME_MAP
        from core.adapter.helpers import mime_to_ext
        assert mime_to_ext("image/bmp", _IMAGE_MIME_MAP, ".png") == ".png"
