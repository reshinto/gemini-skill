"""Tests for adapters/media/music_gen.py — music generation adapter."""
from __future__ import annotations

import base64
import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_audio_response(data=b"audio-data", mime="audio/wav"):
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
            "content": {"parts": [{"text": "Cannot generate music."}], "role": "model"}
        }],
    }


class TestMusicGenGetParser:
    def test_has_prompt(self):
        from adapters.media.music_gen import get_parser
        args = get_parser().parse_args(["upbeat jazz"])
        assert args.prompt == "upbeat jazz"


class TestMusicGenRun:
    def test_dry_run_skips(self, capsys):
        from adapters.media.music_gen import run
        run(prompt="jazz", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_saves_audio_to_file(self, tmp_path, capsys):
        from adapters.media.music_gen import run
        with patch("adapters.media.music_gen.api_call", return_value=_mock_audio_response()), \
             patch("adapters.media.music_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="jazz", execute=True)
        data = json.loads(capsys.readouterr().out)
        assert data["mime_type"] == "audio/wav"
        assert data["size_bytes"] > 0

    def test_sets_audio_modality(self, capsys):
        from adapters.media.music_gen import run
        with patch("adapters.media.music_gen.api_call", return_value=_mock_audio_response()) as mock, \
             patch("adapters.media.music_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="jazz", execute=True)
        body = mock.call_args.kwargs["body"]
        assert body["generationConfig"]["responseModalities"] == ["AUDIO", "TEXT"]

    def test_emits_text_when_no_audio(self, capsys):
        from adapters.media.music_gen import run
        with patch("adapters.media.music_gen.api_call", return_value=_mock_text_only_response()), \
             patch("adapters.media.music_gen.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="jazz", execute=True)
        assert "Cannot generate" in capsys.readouterr().out


class TestMusicMimeToExt:
    def test_known_types(self):
        from adapters.media.music_gen import _mime_to_ext
        assert _mime_to_ext("audio/wav") == ".wav"
        assert _mime_to_ext("audio/mpeg") == ".mp3"

    def test_unknown_defaults_to_wav(self):
        from adapters.media.music_gen import _mime_to_ext
        assert _mime_to_ext("audio/unknown") == ".wav"
