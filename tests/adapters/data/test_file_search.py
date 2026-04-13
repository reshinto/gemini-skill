"""Tests for adapters/data/file_search.py — File Search / RAG adapter."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


class TestFileSearchGetParser:
    def test_has_create_action(self):
        from adapters.data.file_search import get_parser
        args = get_parser().parse_args(["create", "my-store"])
        assert args.action == "create"
        assert args.name == "my-store"

    def test_create_accepts_execute(self):
        from adapters.data.file_search import get_parser

        args = get_parser().parse_args(["create", "my-store", "--execute"])
        assert args.execute is True

    def test_has_upload_action(self):
        from adapters.data.file_search import get_parser
        args = get_parser().parse_args(["upload", "stores/x", "files/abc"])
        assert args.action == "upload"

    def test_upload_accepts_execute(self):
        from adapters.data.file_search import get_parser

        args = get_parser().parse_args(["upload", "stores/x", "files/abc", "--execute"])
        assert args.execute is True

    def test_has_query_action(self):
        from adapters.data.file_search import get_parser
        args = get_parser().parse_args(["query", "search this", "--store", "stores/x"])
        assert args.action == "query"
        assert args.prompt == "search this"

    def test_query_rejects_execute(self):
        from adapters.data.file_search import get_parser

        with pytest.raises(SystemExit):
            get_parser().parse_args(["query", "search this", "--store", "stores/x", "--execute"])

    def test_has_list_action(self):
        from adapters.data.file_search import get_parser
        args = get_parser().parse_args(["list"])
        assert args.action == "list"

    def test_list_rejects_execute(self):
        from adapters.data.file_search import get_parser

        with pytest.raises(SystemExit):
            get_parser().parse_args(["list", "--execute"])

    def test_has_delete_action(self):
        from adapters.data.file_search import get_parser
        args = get_parser().parse_args(["delete", "stores/x"])
        assert args.action == "delete"

    def test_delete_accepts_execute(self):
        from adapters.data.file_search import get_parser

        args = get_parser().parse_args(["delete", "stores/x", "--execute"])
        assert args.execute is True


class TestFileSearchCreate:
    def test_dry_run_skips(self, capsys):
        from adapters.data.file_search import run
        run(action="create", name="store1", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_create_calls_api(self, capsys):
        from adapters.data.file_search import run
        with patch("adapters.data.file_search.api_call", return_value={"name": "stores/x"}):
            run(action="create", name="store1", execute=True)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "stores/x"

    def test_create_no_name_error(self, capsys):
        from adapters.data.file_search import run
        run(action="create", name=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestFileSearchUpload:
    def test_dry_run_skips(self, capsys):
        from adapters.data.file_search import run
        run(action="upload", store="stores/x", file_uri="files/a", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_upload_starts_operation(self, capsys):
        from adapters.data.file_search import run
        with patch("adapters.data.file_search.api_call") as mock_api, \
             patch("adapters.data.file_search._poll_operation") as mock_poll:
            mock_api.return_value = {"name": "operations/op1"}
            run(action="upload", store="stores/x", file_uri="files/a", execute=True)
        mock_poll.assert_called_once_with("operations/op1")

    def test_upload_no_operation_name(self, capsys):
        from adapters.data.file_search import run
        with patch("adapters.data.file_search.api_call", return_value={"result": "ok"}):
            run(action="upload", store="stores/x", file_uri="files/a", execute=True)
        data = json.loads(capsys.readouterr().out)
        assert data["result"] == "ok"

    def test_upload_missing_args_error(self, capsys):
        from adapters.data.file_search import run
        run(action="upload", store=None, file_uri=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestFileSearchQuery:
    def test_query_sends_file_search_tool(self, capsys):
        from adapters.data.file_search import run
        resp = {"candidates": [{"content": {"parts": [{"text": "Found result"}]}}]}
        with patch("adapters.data.file_search.api_call", return_value=resp) as mock, \
             patch("adapters.data.file_search.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=None)
            run(action="query", prompt="find doc", store="stores/x")
        body = mock.call_args.kwargs["body"]
        assert "fileSearch" in body["tools"][0]

    def test_query_missing_args_error(self, capsys):
        from adapters.data.file_search import run
        run(action="query", prompt=None, store=None)
        assert "[ERROR]" in capsys.readouterr().out


class TestFileSearchList:
    def test_list_stores(self, capsys):
        from adapters.data.file_search import run
        with patch("adapters.data.file_search.api_call", return_value={"fileSearchStores": []}):
            run(action="list")
        data = json.loads(capsys.readouterr().out)
        assert data["count"] == 0


class TestFileSearchDelete:
    def test_dry_run_skips(self, capsys):
        from adapters.data.file_search import run
        run(action="delete", name="stores/x", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_delete_calls_api(self, capsys):
        from adapters.data.file_search import run
        with patch("adapters.data.file_search.api_call"):
            run(action="delete", name="stores/x", execute=True)
        assert "Deleted" in capsys.readouterr().out

    def test_delete_no_name_error(self, capsys):
        from adapters.data.file_search import run
        run(action="delete", name=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestFileSearchNoAction:
    def test_no_action_error(self, capsys):
        from adapters.data.file_search import run
        run(action=None)
        assert "[ERROR]" in capsys.readouterr().out


class TestPollOperation:
    def test_poll_returns_on_done(self, capsys):
        from adapters.data.file_search import _poll_operation
        with patch("adapters.data.file_search.api_call", return_value={"done": True, "result": "ok"}), \
             patch("adapters.data.file_search.time.sleep"):
            _poll_operation("ops/1")
        data = json.loads(capsys.readouterr().out)
        assert data["done"] is True

    def test_poll_times_out(self, capsys):
        from adapters.data.file_search import _poll_operation
        with patch("adapters.data.file_search.api_call", return_value={"done": False}), \
             patch("adapters.data.file_search.time.sleep"), \
             patch("adapters.data.file_search.time.time", side_effect=[0, 0, 2000]):
            _poll_operation("ops/1", max_wait=1)
        assert "[POLL TIMEOUT]" in capsys.readouterr().out
