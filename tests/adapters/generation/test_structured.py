"""Tests for adapters/generation/structured.py."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_response(text='{"name": "Alice", "age": 30}'):
    return {
        "candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20, "cachedContentTokenCount": 0},
    }


class TestStructuredGetParser:
    def test_has_prompt_and_schema(self):
        from adapters.generation.structured import get_parser
        args = get_parser().parse_args(["list users", "--schema", '{"type": "object"}'])
        assert args.prompt == "list users"
        assert args.schema == '{"type": "object"}'


class TestStructuredRun:
    def test_sends_schema_in_generation_config(self, capsys):
        from adapters.generation.structured import run
        schema = '{"type": "object", "properties": {"name": {"type": "string"}}}'

        with patch("adapters.generation.structured.api_call", return_value=_mock_response()) as mock_api, \
             patch("adapters.generation.structured.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="list users", schema=schema)

        body = mock_api.call_args.kwargs["body"]
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert "responseSchema" in body["generationConfig"]

    def test_loads_schema_from_file(self, tmp_path, capsys):
        from adapters.generation.structured import run
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"type": "object"}')

        with patch("adapters.generation.structured.api_call", return_value=_mock_response()) as mock_api, \
             patch("adapters.generation.structured.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="list", schema=str(schema_file))

        body = mock_api.call_args.kwargs["body"]
        assert body["generationConfig"]["responseSchema"] == {"type": "object"}

    def test_emits_json_response(self, capsys):
        from adapters.generation.structured import run
        with patch("adapters.generation.structured.api_call", return_value=_mock_response()), \
             patch("adapters.generation.structured.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(prompt="list", schema='{"type": "object"}')
        assert '"name"' in capsys.readouterr().out
