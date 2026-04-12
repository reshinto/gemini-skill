"""Tests for adapters/data/files.py — File API adapter."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


class TestFilesGetParser:
    def test_has_upload_action(self):
        from adapters.data.files import get_parser
        args = get_parser().parse_args(["upload", "test.pdf"])
        assert args.action == "upload"
        assert args.path == "test.pdf"

    def test_has_list_action(self):
        from adapters.data.files import get_parser
        args = get_parser().parse_args(["list"])
        assert args.action == "list"

    def test_has_get_action(self):
        from adapters.data.files import get_parser
        args = get_parser().parse_args(["get", "files/abc"])
        assert args.action == "get"
        assert args.name == "files/abc"

    def test_has_delete_action(self):
        from adapters.data.files import get_parser
        args = get_parser().parse_args(["delete", "files/abc"])
        assert args.action == "delete"


class TestFilesUpload:
    def test_dry_run_skips_upload(self, capsys):
        from adapters.data.files import run
        run(action="upload", path="test.pdf", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_upload_calls_upload_file(self, tmp_path, capsys):
        from adapters.data.files import run
        f = tmp_path / "test.txt"
        f.write_text("content")

        with patch("adapters.data.files.upload_file", return_value={"file": {"name": "files/x", "uri": "gs://x"}}) as mock:
            run(action="upload", path=str(f), execute=True)
        mock.assert_called_once()

    def test_upload_no_path_shows_error(self, capsys):
        from adapters.data.files import run
        run(action="upload", path=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out

    def test_upload_emits_json(self, tmp_path, capsys):
        from adapters.data.files import run
        f = tmp_path / "test.txt"
        f.write_text("content")

        with patch("adapters.data.files.upload_file", return_value={"file": {"name": "files/x", "uri": "gs://x"}}):
            run(action="upload", path=str(f), execute=True)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "files/x"


class TestFilesList:
    def test_list_files(self, capsys):
        from adapters.data.files import run
        with patch("adapters.data.files.api_call", return_value={"files": [{"name": "files/a"}]}):
            run(action="list")
        data = json.loads(capsys.readouterr().out)
        assert data["count"] == 1


class TestFilesGet:
    def test_get_file(self, capsys):
        from adapters.data.files import run
        with patch("adapters.data.files.api_call", return_value={"name": "files/a", "state": "ACTIVE"}):
            run(action="get", name="files/a")
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "files/a"

    def test_get_no_name_shows_error(self, capsys):
        from adapters.data.files import run
        run(action="get", name=None)
        assert "[ERROR]" in capsys.readouterr().out


class TestFilesDelete:
    def test_dry_run_skips_delete(self, capsys):
        from adapters.data.files import run
        run(action="delete", name="files/a", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_delete_calls_api(self, capsys):
        from adapters.data.files import run
        with patch("adapters.data.files.api_call") as mock:
            run(action="delete", name="files/a", execute=True)
        mock.assert_called_once()

    def test_delete_no_name_shows_error(self, capsys):
        from adapters.data.files import run
        run(action="delete", name=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestFilesNoAction:
    def test_no_action_shows_error(self, capsys):
        from adapters.data.files import run
        run(action=None)
        assert "[ERROR]" in capsys.readouterr().out
