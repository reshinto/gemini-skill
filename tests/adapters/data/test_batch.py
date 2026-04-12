"""Tests for adapters/data/batch.py — batch processing adapter."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


class TestBatchGetParser:
    def test_has_create_action(self):
        from adapters.data.batch import get_parser
        args = get_parser().parse_args(["create", "--src", "gs://in", "--dest", "gs://out"])
        assert args.action == "create"
        assert args.src == "gs://in"

    def test_has_list_action(self):
        from adapters.data.batch import get_parser
        args = get_parser().parse_args(["list"])
        assert args.action == "list"

    def test_has_cancel_action(self):
        from adapters.data.batch import get_parser
        args = get_parser().parse_args(["cancel", "batchJobs/abc"])
        assert args.action == "cancel"


class TestBatchCreate:
    def test_dry_run_skips(self, capsys):
        from adapters.data.batch import run
        run(action="create", src="gs://in", dest="gs://out", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_create_calls_api(self, capsys):
        from adapters.data.batch import run
        with patch("adapters.data.batch.api_call", return_value={"name": "batchJobs/x"}):
            run(action="create", src="gs://in", dest="gs://out", execute=True)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "batchJobs/x"

    def test_create_missing_args_error(self, capsys):
        from adapters.data.batch import run
        run(action="create", src=None, dest=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out

    def test_create_with_model(self, capsys):
        from adapters.data.batch import run
        with patch("adapters.data.batch.api_call", return_value={}) as mock:
            run(action="create", src="gs://in", dest="gs://out", model="gemini-2.5-flash", execute=True)
        body = mock.call_args.kwargs["body"]
        assert body["model"] == "models/gemini-2.5-flash"


class TestBatchList:
    def test_list_batches(self, capsys):
        from adapters.data.batch import run
        with patch("adapters.data.batch.api_call", return_value={"batchJobs": []}):
            run(action="list")
        data = json.loads(capsys.readouterr().out)
        assert data["count"] == 0


class TestBatchGet:
    def test_get_batch(self, capsys):
        from adapters.data.batch import run
        with patch("adapters.data.batch.api_call", return_value={"name": "bj/x", "state": "RUNNING"}):
            run(action="get", name="bj/x")
        data = json.loads(capsys.readouterr().out)
        assert data["state"] == "RUNNING"

    def test_get_no_name_error(self, capsys):
        from adapters.data.batch import run
        run(action="get", name=None)
        assert "[ERROR]" in capsys.readouterr().out


class TestBatchCancel:
    def test_dry_run_skips(self, capsys):
        from adapters.data.batch import run
        run(action="cancel", name="bj/x", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_cancel_calls_api(self, capsys):
        from adapters.data.batch import run
        with patch("adapters.data.batch.api_call"):
            run(action="cancel", name="bj/x", execute=True)
        assert "Cancelled" in capsys.readouterr().out

    def test_cancel_no_name_error(self, capsys):
        from adapters.data.batch import run
        run(action="cancel", name=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestBatchNoAction:
    def test_no_action_error(self, capsys):
        from adapters.data.batch import run
        run(action=None)
        assert "[ERROR]" in capsys.readouterr().out
