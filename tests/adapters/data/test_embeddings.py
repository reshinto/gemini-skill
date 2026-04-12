"""Tests for adapters/data/embeddings.py."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


def _mock_embed_response(values=None):
    return {
        "embedding": {"values": values or [0.1, 0.2, 0.3]},
    }


class TestEmbeddingsGetParser:
    def test_has_text_arg(self):
        from adapters.data.embeddings import get_parser
        args = get_parser().parse_args(["hello world"])
        assert args.text == "hello world"

    def test_has_task_type_flag(self):
        from adapters.data.embeddings import get_parser
        args = get_parser().parse_args(["hello", "--task-type", "RETRIEVAL_DOCUMENT"])
        assert args.task_type == "RETRIEVAL_DOCUMENT"


class TestEmbeddingsRun:
    def test_calls_embed_content_endpoint(self, capsys):
        from adapters.data.embeddings import run
        with patch("adapters.data.embeddings.api_call", return_value=_mock_embed_response()) as mock_api, \
             patch("adapters.data.embeddings.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello")

        endpoint = mock_api.call_args[0][0]
        assert "embedContent" in endpoint

    def test_returns_embedding_values(self, capsys):
        from adapters.data.embeddings import run
        import json
        with patch("adapters.data.embeddings.api_call", return_value=_mock_embed_response([0.5, 0.6])), \
             patch("adapters.data.embeddings.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello")

        data = json.loads(capsys.readouterr().out)
        assert data["values"] == [0.5, 0.6]
        assert data["dimensions"] == 2

    def test_sends_task_type_when_provided(self, capsys):
        from adapters.data.embeddings import run
        with patch("adapters.data.embeddings.api_call", return_value=_mock_embed_response()) as mock_api, \
             patch("adapters.data.embeddings.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello", task_type="RETRIEVAL_QUERY")

        body = mock_api.call_args.kwargs["body"]
        assert body["taskType"] == "RETRIEVAL_QUERY"

    def test_no_task_type_by_default(self, capsys):
        from adapters.data.embeddings import run
        with patch("adapters.data.embeddings.api_call", return_value=_mock_embed_response()) as mock_api, \
             patch("adapters.data.embeddings.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello")

        body = mock_api.call_args.kwargs["body"]
        assert "taskType" not in body

    def test_handles_empty_embedding(self, capsys):
        from adapters.data.embeddings import run
        import json
        with patch("adapters.data.embeddings.api_call", return_value={"embedding": {}}), \
             patch("adapters.data.embeddings.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(text="hello")

        data = json.loads(capsys.readouterr().out)
        assert data["values"] == []
        assert data["dimensions"] == 0
