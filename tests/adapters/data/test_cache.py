"""Tests for adapters/data/cache.py — context caching adapter."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


class TestCacheGetParser:
    def test_has_create_action(self):
        from adapters.data.cache import get_parser
        args = get_parser().parse_args(["create", "system prompt text"])
        assert args.action == "create"
        assert args.content == "system prompt text"

    def test_create_accepts_execute(self):
        from adapters.data.cache import get_parser

        args = get_parser().parse_args(["create", "system prompt text", "--execute"])
        assert args.execute is True

    def test_has_list_action(self):
        from adapters.data.cache import get_parser
        args = get_parser().parse_args(["list"])
        assert args.action == "list"

    def test_list_rejects_execute(self):
        from adapters.data.cache import get_parser

        with pytest.raises(SystemExit):
            get_parser().parse_args(["list", "--execute"])

    def test_has_delete_action(self):
        from adapters.data.cache import get_parser
        args = get_parser().parse_args(["delete", "cachedContents/abc"])
        assert args.action == "delete"

    def test_delete_accepts_execute(self):
        from adapters.data.cache import get_parser

        args = get_parser().parse_args(["delete", "cachedContents/abc", "--execute"])
        assert args.execute is True


class TestCacheCreate:
    def test_dry_run_skips(self, capsys):
        from adapters.data.cache import run
        run(action="create", content="text", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_create_calls_api(self, capsys):
        from adapters.data.cache import run
        with patch("adapters.data.cache.api_call", return_value={"name": "cachedContents/x"}) as mock, \
             patch("adapters.data.cache.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False)
            run(action="create", content="text", execute=True)
        assert mock.call_args.kwargs["body"]["ttl"] == "3600s"

    def test_create_no_content_shows_error(self, capsys):
        from adapters.data.cache import run
        run(action="create", content=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestCacheList:
    def test_list_caches(self, capsys):
        from adapters.data.cache import run
        with patch("adapters.data.cache.api_call", return_value={"cachedContents": []}):
            run(action="list")
        data = json.loads(capsys.readouterr().out)
        assert data["count"] == 0


class TestCacheGet:
    def test_get_cache(self, capsys):
        from adapters.data.cache import run
        with patch("adapters.data.cache.api_call", return_value={"name": "cc/x"}):
            run(action="get", name="cc/x")
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "cc/x"

    def test_get_no_name_error(self, capsys):
        from adapters.data.cache import run
        run(action="get", name=None)
        assert "[ERROR]" in capsys.readouterr().out


class TestCacheDelete:
    def test_dry_run_skips(self, capsys):
        from adapters.data.cache import run
        run(action="delete", name="cc/x", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_delete_calls_api(self, capsys):
        from adapters.data.cache import run
        with patch("adapters.data.cache.api_call"):
            run(action="delete", name="cc/x", execute=True)
        assert "Deleted" in capsys.readouterr().out

    def test_delete_no_name_error(self, capsys):
        from adapters.data.cache import run
        run(action="delete", name=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestCacheNoAction:
    def test_no_action_error(self, capsys):
        from adapters.data.cache import run
        run(action=None)
        assert "[ERROR]" in capsys.readouterr().out
